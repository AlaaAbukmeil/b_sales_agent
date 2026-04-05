"""
Simulation runner — the main loop that ties everything together.
"""

import os
import yaml
import time
from datetime import datetime

from src.dify_client import DifyClient
from src.agent.sales_agent import SalesAgent
from src.agent.customer import CustomerSimulator
from src.pipeline.refiner import ScriptRefiner
from src.pipeline.scorer import CallScorer
from src.storage.database import Database


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def load_script(path: str = "scripts/v1.yaml") -> str:
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    return data.get("script", "")


def save_script(script: str, version: int):
    os.makedirs("scripts", exist_ok=True)
    path = f"scripts/v{version}.yaml"
    with open(path, "w") as f:
        yaml.dump({"script": script, "version": version}, f, default_flow_style=False)
    print(f"  💾 Saved {path}")


def run_call(agent: SalesAgent, customer: CustomerSimulator, max_turns: int) -> list:
    """Run a single simulated call and return the transcript."""
    transcript = []

    # Agent opens
    agent_msg = agent.open()
    transcript.append({"role": "agent", "message": agent_msg})
    print(f"    🤖 Agent: {agent_msg[:120]}{'...' if len(agent_msg) > 120 else ''}")

    for turn in range(max_turns):
        # Customer responds
        time.sleep(0.5)  # small delay to avoid rate limits
        cust_msg = customer.respond(agent_msg)
        transcript.append({"role": "customer", "message": cust_msg})
        print(f"    👤 Customer: {cust_msg[:120]}{'...' if len(cust_msg) > 120 else ''}")

        # Check for call-ending signals
        end_phrases = [
            "goodbye", "good bye", "bye ", "bye.", "hang up",
            "end call", "gotta go", "have to go",
        ]
        if any(phrase in cust_msg.lower() for phrase in end_phrases):
            break

        # Agent responds
        time.sleep(0.5)
        agent_msg = agent.respond(cust_msg)
        transcript.append({"role": "agent", "message": agent_msg})
        print(f"    🤖 Agent: {agent_msg[:120]}{'...' if len(agent_msg) > 120 else ''}")

    return transcript


def run_simulation(config: dict = None):
    """Run the full simulation pipeline."""
    if config is None:
        config = load_config()

    dify = config["dify"]
    sim = config["simulation"]

    # Initialize Dify clients
    agent_client = DifyClient(dify["base_url"], dify["sales_agent_api_key"])
    customer_client = DifyClient(dify["base_url"], dify["customer_api_key"])
    refiner_client = DifyClient(dify["base_url"], dify["refiner_api_key"])

    # Initialize components
    current_script = load_script()
    agent = SalesAgent(agent_client, current_script)
    customer = CustomerSimulator(customer_client)
    refiner = ScriptRefiner(refiner_client)
    scorer = CallScorer()
    db = Database()

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    for iteration in range(1, sim["num_iterations"] + 1):
        print(f"\n{'='*60}")
        print(f"  ITERATION {iteration} / {sim['num_iterations']}")
        print(f"{'='*60}")

        all_transcripts = []
        all_scores = []

        for call_num in range(1, sim["calls_per_iteration"] + 1):
            print(f"\n  📞 Call {call_num} / {sim['calls_per_iteration']}")

            # Reset for new call
            agent.reset()
            customer.reset()
            print(f"  🎭 Persona: {customer.persona_name}")

            # Run the call
            transcript = run_call(agent, customer, sim["max_turns_per_call"])

            # Score it
            score = scorer.score(transcript)
            all_transcripts.append(transcript)
            all_scores.append(score)

            print(f"  📊 Score: overall={score['overall']} | "
                  f"engage={score['engagement']} | "
                  f"objection={score['objection_handling']} | "
                  f"discovery={score['discovery']} | "
                  f"close={score['closing']} | "
                  f"appt={'✅' if score['got_appointment'] else '❌'}")

            # Save to database
            db.save_call(
                run_id=run_id,
                iteration=iteration,
                call_number=call_num,
                persona=customer.persona_name,
                persona_prompt=customer.persona_prompt,
                transcript=transcript,
                scores=score,
            )

        # Aggregate metrics
        avg_metrics = scorer.aggregate(all_scores)
        db.save_iteration(run_id, iteration, avg_metrics)

        print(f"\n  📈 Iteration {iteration} Summary:")
        print(f"     Avg Overall:           {avg_metrics['overall']:.2f} / 10")
        print(f"     Avg Engagement:        {avg_metrics['engagement']:.2f} / 10")
        print(f"     Avg Objection Handling: {avg_metrics['objection_handling']:.2f} / 10")
        print(f"     Avg Discovery:         {avg_metrics['discovery']:.2f} / 10")
        print(f"     Avg Closing:           {avg_metrics['closing']:.2f} / 10")
        print(f"     Appointment Rate:      {avg_metrics['appointment_rate']:.0%}")

        # Refine script (skip on last iteration)
        if iteration < sim["num_iterations"]:
            print(f"\n  🔧 Refining script...")
            try:
                new_script = refiner.refine(current_script, all_transcripts, avg_metrics)
                current_script = new_script
                agent.set_script(new_script)
                save_script(new_script, iteration + 1)
            except Exception as e:
                print(f"  ⚠️  Refinement failed: {e}")
                print(f"  ⚠️  Continuing with current script.")

    # Final summary
    print(f"\n{'='*60}")
    print(f"  ✅ SIMULATION COMPLETE")
    print(f"  Run ID: {run_id}")
    print(f"  Scripts saved: scripts/v1.yaml through scripts/v{sim['num_iterations']}.yaml")
    print(f"  Database: data/calls.db")
    print(f"  Run `python main.py --report` for full report")
    print(f"{'='*60}")