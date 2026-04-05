"""
Main orchestration: runs the full self-improving call center demo.
"""

import json
import os
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule

from src.llm_client import get_config
from src.agent.sales_agent import SalesAgent
from src.agent.customer_simulator import CustomerSimulator
from src.pipeline.conversation_runner import ConversationRunner
from src.pipeline.outcome_evaluator import OutcomeEvaluator
from src.pipeline.script_optimizer import ScriptOptimizer
from src.storage.db import init_db, store_call, store_iteration, get_iteration_stats
from src.storage.script_store import load_script, save_script, validate_script

console = Console()


def load_personas() -> list:
    with open("data/personas.json", "r", encoding="utf-8") as f:
        return json.load(f)


def display_transcript(transcript: list, persona_name: str):
    """Pretty-print a conversation transcript."""
    for turn in transcript:
        if turn["role"] == "agent":
            console.print(Panel(
                turn["content"],
                title="🤖 Agent Alex",
                border_style="blue",
                padding=(0, 1),
            ))
        else:
            console.print(Panel(
                turn["content"],
                title=f"👤 {persona_name}",
                border_style="green",
                padding=(0, 1),
            ))


def display_evaluation(evaluation: dict):
    """Pretty-print call evaluation."""
    emoji = {"success": "✅", "partial": "⚠️", "failed": "❌"}.get(
        evaluation.get("outcome", ""), "❓"
    )
    console.print(
        f"\n  {emoji} **{evaluation.get('outcome', 'unknown').upper()}** — "
        f"{evaluation.get('outcome_detail', 'N/A')}"
    )

    objections = evaluation.get("objections_raised", [])
    if objections:
        tbl = Table(title="Objections Raised", show_lines=True, expand=True)
        tbl.add_column("Type", style="cyan", max_width=15)
        tbl.add_column("Handled?", justify="center", max_width=10)
        tbl.add_column("Suggestion", max_width=50)
        for obj in objections:
            eff = "✅ Yes" if obj.get("effective") else "❌ No"
            tbl.add_row(
                obj.get("type", "?"),
                eff,
                obj.get("suggestion", "—") or "—",
            )
        console.print(tbl)

    strengths = evaluation.get("strengths", [])
    if strengths:
        console.print(f"  💪 Strengths: {'; '.join(strengths)}")

    weaknesses = evaluation.get("weaknesses", [])
    if weaknesses:
        console.print(f"  📉 Weaknesses: {'; '.join(weaknesses)}")


def display_iteration_summary(iteration: int, evaluations: list):
    total = len(evaluations)
    successes = sum(1 for e in evaluations if e.get("outcome") == "success")
    partials = sum(1 for e in evaluations if e.get("outcome") == "partial")
    failures = total - successes - partials
    rate = round(successes / total * 100) if total else 0

    summary = (
        f"Calls: {total}  |  ✅ Success: {successes}  |  "
        f"⚠️ Partial: {partials}  |  ❌ Failed: {failures}\n"
        f"Success Rate: {rate}%"
    )
    console.print(Panel(summary, title=f"📊 Iteration {iteration + 1} Summary",
                        border_style="yellow"))


def display_final_report():
    stats = get_iteration_stats()
    if not stats:
        console.print("[dim]No iteration data found.[/dim]")
        return

    console.print(Rule("[bold]FINAL REPORT[/bold]"))
    tbl = Table(title="Performance Across Iterations", show_lines=True)
    tbl.add_column("Iteration", justify="center")
    tbl.add_column("Script", justify="center")
    tbl.add_column("Calls", justify="center")
    tbl.add_column("✅", justify="center")
    tbl.add_column("⚠️", justify="center")
    tbl.add_column("❌", justify="center")
    tbl.add_column("Success %", justify="center")

    for row in stats:
        _, iter_num, script_v, total, success, partial, failed, _ = row
        rate = f"{round(success / total * 100)}%" if total else "0%"
        tbl.add_row(
            str(iter_num + 1), f"v{script_v}", str(total),
            str(success), str(partial), str(failed), rate,
        )

    console.print(tbl)
    console.print("\n[bold green]✨ Demo complete![/bold green]")
    console.print("[dim]Transcripts: data/transcripts/  |  Scripts: scripts/[/dim]")


def save_transcript(iteration: int, call_idx: int, persona: dict,
                    script_version: int, transcript: list, evaluation: dict):
    os.makedirs("data/transcripts", exist_ok=True)
    path = f"data/transcripts/iter{iteration + 1}_call{call_idx + 1}_{persona['id']}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "iteration": iteration + 1,
            "script_version": script_version,
            "persona": persona,
            "transcript": transcript,
            "evaluation": evaluation,
            "timestamp": datetime.now().isoformat(),
        }, f, indent=2, ensure_ascii=False)


def main():
    config = get_config()
    sim = config["simulation"]
    product = config["product"]

    init_db()
    personas = load_personas()

    num_iterations = sim["num_iterations"]
    calls_per_iter = sim["calls_per_iteration"]
    max_turns = sim["max_turns_per_call"]

    console.print(Rule("[bold cyan]🚀 Self-Improving Call Center Agent[/bold cyan]"))
    console.print(f"  Product: [bold]{product['name']}[/bold]")
    console.print(f"  Iterations: {num_iterations}  |  Calls/iter: {calls_per_iter}  |  Max turns: {max_turns}")
    console.print(f"  Model: {config['deepseek']['model']}\n")

    evaluator = OutcomeEvaluator()
    optimizer = ScriptOptimizer()
    current_script = load_script(1)

    for iteration in range(num_iterations):
        v = current_script.get("version", 1)
        console.print(Rule(f"[bold]ITERATION {iteration + 1}  •  Script v{v}[/bold]"))

        evaluations = []

        for call_idx in range(calls_per_iter):
            persona = personas[call_idx % len(personas)]
            console.print(
                f"\n[bold]📞 Call {call_idx + 1}/{calls_per_iter}: "
                f"{persona['name']} — {persona['role']} at {persona['company']}[/bold]"
            )

            # Build agents
            agent = SalesAgent(current_script, product)
            customer = CustomerSimulator(persona)

            # Run call
            runner = ConversationRunner(agent, customer, max_turns=max_turns)
            transcript = runner.run()

            display_transcript(transcript, persona["name"])

            # Evaluate
            console.print("[dim]  Evaluating...[/dim]")
            evaluation = evaluator.evaluate(transcript, v)
            evaluations.append(evaluation)

            display_evaluation(evaluation)

            # Persist
            store_call(iteration, v, persona, transcript, evaluation)
            save_transcript(iteration, call_idx, persona, v, transcript, evaluation)

        # Iteration summary
        display_iteration_summary(iteration, evaluations)

        # Store iteration stats
        total = len(evaluations)
        s = sum(1 for e in evaluations if e.get("outcome") == "success")
        p = sum(1 for e in evaluations if e.get("outcome") == "partial")
        f = total - s - p
        store_iteration(iteration, v, total, s, p, f)

        # Optimize script (skip after last iteration)
        if iteration < num_iterations - 1:
            console.print("\n[bold yellow]🔧 Optimizing script...[/bold yellow]")
            new_script = optimizer.optimize(current_script, evaluations)

            if new_script.get("version", 0) <= v:
                new_script["version"] = v + 1

            if not validate_script(new_script):
                console.print("[red]  ⚠ Optimized script has invalid structure, carrying forward previous.[/red]")
                new_script = dict(current_script)
                new_script["version"] = v + 1
                new_script["changes_from_previous"] = "Validation failed — carried forward"

            save_script(new_script)
            changes = new_script.get("changes_from_previous", "No changes documented")
            console.print(Panel(str(changes), title="📝 Script Changes v{} → v{}".format(v, new_script["version"]),
                                border_style="magenta"))
            current_script = new_script

    display_final_report()