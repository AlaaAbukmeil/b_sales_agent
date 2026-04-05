"""
Interactive mode: YOU play the customer against the AI sales agent.
Optionally with TTS so the agent "speaks" to you.

Run:  python run_interactive.py
"""

import sys
import os
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console
from rich.panel import Panel

from src.llm_client import get_config
from src.agent.sales_agent import SalesAgent
from src.storage.script_store import load_latest_script, load_script

console = Console()


def play_audio(path: str):
    """Try to play an audio file on Windows."""
    try:
        os.startfile(path)
    except Exception:
        pass


def main():
    config = get_config()
    product = config["product"]
    voice_enabled = config.get("voice", {}).get("enabled", False)
    voice_name = config.get("voice", {}).get("tts_voice", "en-US-AriaNeural")

    try:
        script = load_latest_script()
    except FileNotFoundError:
        script = load_script(1)

    console.print(Rule("[bold cyan]🎙️ Interactive Call — You Are the Customer[/bold cyan]"))
    console.print(f"  Script version: v{script.get('version', '?')}")
    console.print(f"  Voice TTS: {'ON' if voice_enabled else 'OFF'}")
    console.print("  Type your responses. Type [bold]quit[/bold] to end.\n")

    agent = SalesAgent(script, product)

    # Agent opens
    opening = agent.get_opening("Customer", "your company")
    console.print(Panel(opening, title="🤖 Agent Alex", border_style="blue"))

    if voice_enabled:
        from src.voice.tts import speak
        audio_path = speak(opening, voice=voice_name)
        if audio_path:
            play_audio(audio_path)

    # Conversation loop
    while True:
        user_input = console.input("\n[bold green]You:[/bold green] ").strip()
        if not user_input or user_input.lower() in ("quit", "exit", "bye"):
            console.print("[dim]Call ended.[/dim]")
            break

        response = agent.respond(user_input)
        console.print(Panel(response, title="🤖 Agent Alex", border_style="blue"))

        if voice_enabled:
            from src.voice.tts import speak
            audio_path = speak(response, voice=voice_name)
            if audio_path:
                play_audio(audio_path)


if __name__ == "__main__":
    from rich.rule import Rule
    main()