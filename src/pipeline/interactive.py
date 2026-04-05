"""
Interactive mode — the user plays the customer against the AI sales agent.
Supports voice (ElevenLabs TTS + STT) or text-only input.
Now contributes to the script refinement pipeline.
"""

import yaml
from datetime import datetime

from src.dify_client import DifyClient
from src.agent.sales_agent import SalesAgent
from src.pipeline.scorer import CallScorer
from src.pipeline.refiner import ScriptRefiner
from src.pipeline.runner import save_script
from src.storage.database import Database


def load_script(path: str = "scripts/v1.yaml") -> str:
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    return data.get("script", "")


def _find_latest_script() -> tuple:
    """Find the highest-versioned script file. Returns (script_text, version_number)."""
    import os
    scripts_dir = "scripts"
    if not os.path.isdir(scripts_dir):
        return load_script(), 1
    versions = []
    for fname in os.listdir(scripts_dir):
        if fname.startswith("v") and fname.endswith(".yaml"):
            try:
                versions.append(int(fname[1:-5]))
            except ValueError:
                pass
    if not versions:
        return load_script(), 1
    latest = max(versions)
    return load_script(f"scripts/v{latest}.yaml"), latest


def _run_text_call(agent: SalesAgent) -> list:
    """Run a single interactive text call. Returns the transcript."""
    transcript = []

    opening = agent.open()
    transcript.append({"role": "agent", "message": opening})
    print(f"\n🤖 Agent: {opening}")

    while True:
        try:
            user_text = input("\n🧑 You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n📞 Call ended.")
            break

        if not user_text or user_text.lower() in ("quit", "exit", "bye", "goodbye"):
            transcript.append({"role": "customer", "message": user_text or "goodbye"})
            print("\n📞 Call ended.")
            break

        transcript.append({"role": "customer", "message": user_text})

        response = agent.respond(user_text)
        transcript.append({"role": "agent", "message": response})
        print(f"\n🤖 Agent: {response}")

    return transcript


def _run_voice_call(agent: SalesAgent, tts, stt) -> list:
    """Run a single interactive voice call. Returns the transcript."""
    transcript = []

    opening = agent.open()
    transcript.append({"role": "agent", "message": opening})
    print(f"\n🤖 Agent: {opening}")
    tts.speak(opening)

    while True:
        user_text = stt.listen()
        print(f"\n🧑 You: {user_text}")

        if not user_text or "quit" in user_text.lower() or "goodbye" in user_text.lower():
            transcript.append({"role": "customer", "message": user_text or "goodbye"})
            print("\n📞 Call ended.")
            break

        transcript.append({"role": "customer", "message": user_text})

        response = agent.respond(user_text)
        transcript.append({"role": "agent", "message": response})
        print(f"\n🤖 Agent: {response}")
        tts.speak(response)

    return transcript


def _refine_and_save(
    refiner: ScriptRefiner,
    scorer: CallScorer,
    agent: SalesAgent,
    db: Database,
    run_id: str,
    current_script: str,
    current_version: int,
    session_transcripts: list,
    session_scores: list,
) -> tuple:
    """
    Run refinement on accumulated session data.
    Returns (new_script, new_version, cleared_transcripts, cleared_scores).
    """
    avg_metrics = scorer.aggregate(session_scores)

    print(f"\n  📈 Session Summary ({len(session_transcripts)} call(s)):")
    print(f"     Avg Overall:           {avg_metrics['overall']:.2f} / 10")
    print(f"     Avg Engagement:        {avg_metrics['engagement']:.2f} / 10")
    print(f"     Avg Objection Handling: {avg_metrics['objection_handling']:.2f} / 10")
    print(f"     Avg Discovery:         {avg_metrics['discovery']:.2f} / 10")
    print(f"     Avg Closing:           {avg_metrics['closing']:.2f} / 10")
    print(f"     Appointment Rate:      {avg_metrics['appointment_rate']:.0%}")

    print(f"\n  🔧 Refining script...")
    new_script = refiner.refine(current_script, session_transcripts, avg_metrics)
    new_version = current_version + 1
    agent.set_script(new_script)
    save_script(new_script, new_version)

    db.save_iteration(run_id, new_version, avg_metrics)

    print(f"  ✅ Script refined! Now using v{new_version}")
    return new_script, new_version, [], []


def run_interactive(config: dict):
    """Entry point for interactive mode with script refinement integration."""
    dify = config["dify"]
    has_voice = "elevenlabs" in config and config["elevenlabs"].get("api_key")

    # Choose input mode
    use_voice = False
    if has_voice:
        print("\nInput mode:")
        print("  1) Voice (speak & listen via ElevenLabs)")
        print("  2) Text (type your responses)")
        choice = input("Choose [1/2]: ").strip()
        use_voice = (choice == "1")

    # Setup voice engines if needed
    tts, stt = None, None
    if use_voice:
        from src.voice import TTSEngine, STTEngine
        tts = TTSEngine(
            api_key=config["elevenlabs"]["api_key"],
            voice_id=config["elevenlabs"]["voice_id"],
            model_id=config["elevenlabs"].get("model_id", "eleven_multilingual_v2"),
        )
        stt = STTEngine(
            api_key=config["elevenlabs"]["api_key"],
            sample_rate=config.get("voice", {}).get("sample_rate", 16000),
            record_seconds=config.get("voice", {}).get("record_seconds", 30),
            silence_duration=config.get("voice", {}).get("silence_duration", 1.8),
            silence_threshold_multiplier=config.get("voice", {}).get("silence_threshold", 1.5),
        )

    # Initialize shared components
    agent_client = DifyClient(base_url=dify["base_url"], api_key=dify["sales_agent_api_key"])
    refiner_client = DifyClient(base_url=dify["base_url"], api_key=dify["refiner_api_key"])

    current_script, current_version = _find_latest_script()
    agent = SalesAgent(agent_client, current_script)
    scorer = CallScorer()
    refiner = ScriptRefiner(refiner_client)
    db = Database()

    run_id = f"interactive_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    session_transcripts = []
    session_scores = []
    call_count = 0

    while True:
        call_count += 1
        print(f"\n{'='*50}")
        print(f"  INTERACTIVE CALL #{call_count}")
        print(f"  Script version: v{current_version}")
        print(f"  Mode: {'Voice' if use_voice else 'Text'}")
        print(f"{'='*50}")

        # Reset agent for new call
        agent.reset()

        # Run the call
        if use_voice:
            transcript = _run_voice_call(agent, tts, stt)
        else:
            transcript = _run_text_call(agent)

        if len(transcript) < 2:
            print("  ⚠️  Call too short to score. Skipping.")
            call_count -= 1
            continue

        # Score the call
        score = scorer.score(transcript)
        session_transcripts.append(transcript)
        session_scores.append(score)

        print(f"\n  📊 Call Score:")
        print(f"     Overall:           {score['overall']:.1f} / 10")
        print(f"     Engagement:        {score['engagement']:.1f} / 10")
        print(f"     Objection Handling: {score['objection_handling']:.1f} / 10")
        print(f"     Discovery:         {score['discovery']:.1f} / 10")
        print(f"     Closing:           {score['closing']:.1f} / 10")
        print(f"     Appointment:       {'✅' if score['got_appointment'] else '❌'}")

        # Save to database
        db.save_call(
            run_id=run_id,
            iteration=current_version,
            call_number=call_count,
            persona="interactive_user",
            persona_prompt="Real user playing customer role",
            transcript=transcript,
            scores=score,
        )

        # Post-call menu
        print(f"\n  What next?")
        print(f"  1) Make another call (same script)")
        print(f"  2) Refine script & continue ({len(session_transcripts)} call(s) queued)")
        print(f"  3) Refine script & quit")
        print(f"  4) Quit without refining")

        try:
            action = input("  Choose [1/2/3/4]: ").strip()
        except (EOFError, KeyboardInterrupt):
            action = "4"

        if action == "2":
            try:
                current_script, current_version, session_transcripts, session_scores = (
                    _refine_and_save(
                        refiner, scorer, agent, db, run_id,
                        current_script, current_version,
                        session_transcripts, session_scores,
                    )
                )
            except Exception as e:
                print(f"  ⚠️  Refinement failed: {e}")
                print(f"  Continuing with current script v{current_version}.")
            # Loop continues → next call

        elif action == "3":
            try:
                current_script, current_version, session_transcripts, session_scores = (
                    _refine_and_save(
                        refiner, scorer, agent, db, run_id,
                        current_script, current_version,
                        session_transcripts, session_scores,
                    )
                )
            except Exception as e:
                print(f"  ⚠️  Refinement failed: {e}")
            break

        elif action == "4":
            if session_transcripts:
                avg_metrics = scorer.aggregate(session_scores)
                db.save_iteration(run_id, current_version, avg_metrics)
                print(f"\n  💾 Session scores saved ({len(session_transcripts)} call(s)).")
            break

        # action == "1" (or anything else) → just loop again

    print(f"\n{'='*50}")
    print(f"  ✅ Interactive session complete")
    print(f"  Run ID: {run_id}")
    print(f"  Total calls: {call_count}")
    print(f"  Final script version: v{current_version}")
    print(f"{'='*50}")