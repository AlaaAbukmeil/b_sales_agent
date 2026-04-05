"""
Sales Call Simulation — Main Entry Point
Single entry point: choose between automated simulation, interactive call, or report.
"""

import argparse
import sys
from src.pipeline.runner import run_simulation, load_config


def main():
    parser = argparse.ArgumentParser(description="Sales Call Simulation Engine")
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to config file (default: config.yaml)",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=None,
        help="Override number of iterations from config",
    )
    parser.add_argument(
        "--calls",
        type=int,
        default=None,
        help="Override calls per iteration from config",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print a summary report from the database instead of running",
    )
    parser.add_argument(
        "--mode",
        choices=["simulate", "interactive"],
        default=None,
        help="Skip the menu and go straight to a mode",
    )
    args = parser.parse_args()

    if args.report:
        print_report()
        return

    config = load_config(args.config)
    if args.iterations is not None:
        config["simulation"]["num_iterations"] = args.iterations
    if args.calls is not None:
        config["simulation"]["calls_per_iteration"] = args.calls

    # Determine mode
    mode = args.mode
    if mode is None:
        print("=" * 50)
        print("  SALES CALL ENGINE")
        print("=" * 50)
        print("  1) Simulated  — automated calls, scoring, and script refinement")
        print("  2) Interactive — you play the customer against the AI agent")
        print("  3) Report     — view results from previous runs")
        print()
        choice = input("  Choose [1/2/3]: ").strip()
        if choice == "2":
            mode = "interactive"
        elif choice == "3":
            print_report()
            return
        else:
            mode = "simulate"

    if mode == "interactive":
        from src.pipeline.interactive import run_interactive
        run_interactive(config)
    else:
        print("=" * 60)
        print("  SALES CALL SIMULATION ENGINE")
        print("=" * 60)
        print(f"  Iterations:       {config['simulation']['num_iterations']}")
        print(f"  Calls/iteration:  {config['simulation']['calls_per_iteration']}")
        print(f"  Max turns/call:   {config['simulation']['max_turns_per_call']}")
        print(f"  Dify base URL:    {config['dify']['base_url']}")
        print("=" * 60)

        try:
            run_simulation(config)
        except KeyboardInterrupt:
            print("\n\n⚠️  Simulation interrupted by user.")
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ Simulation failed: {e}")
            raise


def print_report():
    """Print a summary report from stored data."""
    from src.storage.database import Database

    db = Database()
    report = db.get_report()

    print("=" * 60)
    print("  SIMULATION REPORT")
    print("=" * 60)

    if not report:
        print("  No data found. Run a simulation first.")
        return

    for iteration_data in report:
        it = iteration_data["iteration"]
        calls = iteration_data["calls"]
        avg = iteration_data["avg_scores"]

        print(f"\n--- Iteration {it} ({len(calls)} calls) ---")
        print(f"  Avg Engagement:        {avg.get('engagement', 0):.2f} / 10")
        print(f"  Avg Objection Handling: {avg.get('objection_handling', 0):.2f} / 10")
        print(f"  Avg Discovery:         {avg.get('discovery', 0):.2f} / 10")
        print(f"  Avg Closing:           {avg.get('closing', 0):.2f} / 10")
        print(f"  Avg Overall:           {avg.get('overall', 0):.2f} / 10")
        print(f"  Appointment Rate:      {avg.get('appointment_rate', 0):.0%}")

        for call in calls:
            outcome = "✅ Appointment" if call["scores"].get("got_appointment") else "❌ No appointment"
            print(f"    Call {call['call_number']}: {outcome} | Overall: {call['scores'].get('overall', 0):.1f} | Persona: {call['persona'][:50]}...")

    print()


if __name__ == "__main__":
    main()