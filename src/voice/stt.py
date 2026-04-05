"""
Speech-to-Text mock for prototyping.
For production: integrate FunASR or local Whisper.
"""


def listen_keyboard() -> str:
    """Mock STT: get input from keyboard."""
    return input("You (customer): ")