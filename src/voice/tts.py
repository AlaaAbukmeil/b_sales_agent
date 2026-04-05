"""
Text-to-Speech wrapper using edge-tts (works globally, free).
Optional — only used when voice mode is enabled.
"""

import asyncio

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False


async def _speak_async(text: str, voice: str = "en-US-AriaNeural",
                       output_file: str = "data/agent_speech.mp3"):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)
    return output_file


def speak(text: str, voice: str = "en-US-AriaNeural",
          output_file: str = "data/agent_speech.mp3") -> str:
    """Convert text to speech and save as MP3. Returns file path."""
    if not EDGE_TTS_AVAILABLE:
        print("[TTS unavailable — install edge-tts]")
        return ""
    return asyncio.run(_speak_async(text, voice, output_file))