import io
import sounddevice as sd
import soundfile as sf
from elevenlabs import ElevenLabs


class TTSEngine:
    def __init__(self, api_key: str, voice_id: str, model_id: str = "eleven_multilingual_v2"):
        self.client = ElevenLabs(api_key=api_key)
        self.voice_id = voice_id
        self.model_id = model_id

    def speak(self, text: str):
        """Convert text to speech and play through speakers."""
        audio_generator = self.client.text_to_speech.convert(
            voice_id=self.voice_id,
            text=text,
            model_id=self.model_id,
            output_format="pcm_22050",
        )

        # Collect all chunks into a single bytes buffer
        audio_bytes = b"".join(chunk for chunk in audio_generator)

        # Convert raw PCM to numpy array and play
        import numpy as np
        audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        sd.play(audio_array, samplerate=22050)
        sd.wait()