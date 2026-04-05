"""
Speech-to-Text engine with smart silence detection.
Records from the microphone, automatically stops when the speaker goes silent,
and transcribes using ElevenLabs STT.
"""

import tempfile
import numpy as np
import sounddevice as sd
import soundfile as sf
from elevenlabs import ElevenLabs


class STTEngine:
    def __init__(
        self,
        api_key: str,
        sample_rate: int = 16000,
        record_seconds: int = 30,
        silence_threshold_multiplier: float = 1.5,
        silence_duration: float = 1.8,
        calibration_duration: float = 0.5,
        chunk_duration: float = 0.1,
        min_speech_duration: float = 0.3,
        pre_speech_buffer: float = 0.3,
    ):
        """
        Args:
            api_key:                      ElevenLabs API key.
            sample_rate:                  Audio sample rate in Hz.
            record_seconds:               Maximum recording time (hard cutoff).
            silence_threshold_multiplier: How many times above the ambient noise floor
                                          a chunk must be to count as speech.
            silence_duration:             Seconds of consecutive silence before stopping.
            calibration_duration:         Seconds of ambient noise to sample at the start.
            chunk_duration:               Length of each audio analysis chunk in seconds.
            min_speech_duration:          Minimum speech length to accept (avoids tiny blips).
            pre_speech_buffer:            Seconds of audio to keep before speech starts
                                          (captures the very beginning of words).
        """
        self.client = ElevenLabs(api_key=api_key)
        self.sample_rate = sample_rate
        self.record_seconds = record_seconds
        self.silence_threshold_multiplier = silence_threshold_multiplier
        self.silence_duration = silence_duration
        self.calibration_duration = calibration_duration
        self.chunk_duration = chunk_duration
        self.min_speech_duration = min_speech_duration
        self.pre_speech_buffer = pre_speech_buffer

    def _rms(self, audio: np.ndarray) -> float:
        """Compute root-mean-square energy of an audio chunk."""
        if len(audio) == 0:
            return 0.0
        return float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))

    def _calibrate_noise_floor(self) -> float:
        """
        Record a short sample of ambient noise and return the RMS level.
        This is used as the baseline for silence detection.
        """
        num_samples = int(self.sample_rate * self.calibration_duration)
        print("  🔇 Calibrating noise floor...", end=" ", flush=True)
        ambient = sd.rec(num_samples, samplerate=self.sample_rate, channels=1, dtype="int16")
        sd.wait()
        noise_rms = self._rms(ambient.flatten())
        # Set a minimum floor so a perfectly silent room doesn't make the
        # threshold impossibly low
        noise_rms = max(noise_rms, 50.0)
        print(f"done (baseline RMS: {noise_rms:.0f})")
        return noise_rms

    def _level_bar(self, rms: float, threshold: float, width: int = 20) -> str:
        """Build a small visual level meter for terminal feedback."""
        # Normalize to a 0..width scale (cap at width)
        level = min(int((rms / max(threshold * 3, 1)) * width), width)
        bar = "█" * level + "░" * (width - level)
        marker = "│" + " " * min(int((threshold / max(threshold * 3, 1)) * width) - 1, width - 1) if threshold > 0 else ""
        return bar

    def listen(self) -> str:
        """
        Record from the microphone with automatic silence detection, then
        transcribe using ElevenLabs STT.

        Flow:
          1. Calibrate the ambient noise floor.
          2. Wait for the user to start speaking.
          3. Record until silence is detected (or max time).
          4. Transcribe and return the text.
        """
        noise_floor = self._calibrate_noise_floor()
        threshold = noise_floor * self.silence_threshold_multiplier

        chunk_samples = int(self.sample_rate * self.chunk_duration)
        max_chunks = int(self.record_seconds / self.chunk_duration)
        silence_chunks_needed = int(self.silence_duration / self.chunk_duration)
        min_speech_chunks = int(self.min_speech_duration / self.chunk_duration)
        pre_buffer_chunks = int(self.pre_speech_buffer / self.chunk_duration)

        all_chunks = []
        speech_started = False
        speech_chunk_count = 0
        silent_chunk_count = 0

        print("🎤 Listening... (speak now)")

        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=chunk_samples,
            ) as stream:
                for i in range(max_chunks):
                    data, overflowed = stream.read(chunk_samples)
                    chunk = data.flatten()
                    chunk_rms = self._rms(chunk)

                    is_speech = chunk_rms > threshold

                    if not speech_started:
                        # Keep a rolling buffer so we don't clip the start of speech
                        all_chunks.append(chunk)
                        if len(all_chunks) > pre_buffer_chunks:
                            all_chunks.pop(0)

                        if is_speech:
                            speech_started = True
                            speech_chunk_count = 1
                            silent_chunk_count = 0
                            bar = self._level_bar(chunk_rms, threshold)
                            print(f"\r  🔊 Speaking {bar}  ", end="", flush=True)
                        else:
                            bar = self._level_bar(chunk_rms, threshold)
                            print(f"\r  ⏳ Waiting  {bar}  ", end="", flush=True)
                    else:
                        all_chunks.append(chunk)

                        if is_speech:
                            speech_chunk_count += 1
                            silent_chunk_count = 0
                            bar = self._level_bar(chunk_rms, threshold)
                            print(f"\r  🔊 Speaking {bar}  ", end="", flush=True)
                        else:
                            silent_chunk_count += 1
                            bar = self._level_bar(chunk_rms, threshold)
                            remaining = (silence_chunks_needed - silent_chunk_count) * self.chunk_duration
                            print(f"\r  🔇 Silence  {bar} ({remaining:.1f}s)", end="", flush=True)

                            if silent_chunk_count >= silence_chunks_needed:
                                print("\r  ⏹  Silence detected — done recording.       ")
                                break

                # Max time reached
                else:
                    print(f"\r  ⏹  Max recording time ({self.record_seconds}s) reached.       ")

        except KeyboardInterrupt:
            print("\n  ⏹  Stopped recording (Ctrl+C).")

        if not all_chunks:
            print("  ⚠️  No audio captured.")
            return ""

        # Assemble the final recording
        recording = np.concatenate(all_chunks)

        # Check if we got enough actual speech
        if not speech_started or speech_chunk_count < min_speech_chunks:
            duration = len(recording) / self.sample_rate
            print(f"  ⚠️  No clear speech detected ({duration:.1f}s captured, {speech_chunk_count} speech chunks).")
            # Still attempt transcription — the user may have spoken softly
            if speech_chunk_count == 0:
                return ""

        duration = len(recording) / self.sample_rate
        print(f"  📝 Transcribing {duration:.1f}s of audio...")

        # Write to temporary WAV file for the ElevenLabs API
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        sf.write(tmp.name, recording, self.sample_rate)

        try:
            with open(tmp.name, "rb") as f:
                result = self.client.speech_to_text.convert(
                    file=f,
                    model_id="scribe_v1",
                    language_code="en",
                )
            text = result.text.strip()
        except Exception as e:
            print(f"  ⚠️  Transcription failed: {e}")
            text = ""
        finally:
            import os
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

        return text