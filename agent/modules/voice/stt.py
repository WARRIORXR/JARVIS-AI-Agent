"""
J.A.R.V.I.S. — Speech-to-Text Module
Primary:  Local OpenAI Whisper (offline, private)
Fallback: Google Speech Recognition (requires internet)
"""

import logging
import time
from typing import Optional

import numpy as np

logger = logging.getLogger('jarvis.stt')


class SpeechToText:
    """
    Handles audio capture and speech transcription.
    Uses local Whisper for privacy-first, offline transcription.
    Falls back to Google STT if Whisper is unavailable.
    """

    def __init__(self, model_size: str = 'base', sample_rate: int = 16000):
        self.sample_rate  = sample_rate
        self.model_size   = model_size
        self._model       = None   # lazy-loaded on first use

    def _load_model(self):
        """Lazy-load Whisper model (only on first transcription call)."""
        if self._model is None:
            try:
                import whisper
                logger.info(f'Loading Whisper "{self.model_size}" model — first run may take a moment...')
                self._model = whisper.load_model(self.model_size)
                logger.info('Whisper model loaded successfully.')
            except ImportError:
                logger.warning('openai-whisper not installed. Using Google STT fallback.')
                self._model = 'google_fallback'
        return self._model

    # ── Wake Word Detection ────────────────────────────────────

    def wait_for_wake_word(self, wake_word: str = 'jarvis') -> bool:
        """
        Block until the wake word is spoken.
        Uses lightweight Google STT for continuous listening.
        Returns True when detected.
        """
        import speech_recognition as sr

        recognizer = sr.Recognizer()
        recognizer.energy_threshold        = 300
        recognizer.dynamic_energy_threshold = True
        mic = sr.Microphone()

        logger.info(f'Idle — listening for wake word: "{wake_word.upper()}"')
        with mic as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)

        while True:
            try:
                with mic as source:
                    audio = recognizer.listen(source, timeout=6, phrase_time_limit=4)
                heard = recognizer.recognize_google(audio).lower()
                logger.debug(f'Heard: "{heard}"')
                if wake_word in heard:
                    logger.info(f'✅ Wake word "{wake_word}" detected.')
                    return True
            except sr.WaitTimeoutError:
                continue
            except sr.UnknownValueError:
                continue
            except sr.RequestError as e:
                logger.error(f'STT request error: {e}')
                time.sleep(2)
            except Exception as e:
                logger.error(f'Wake word listener error: {e}')
                time.sleep(1)

    # ── Audio Recording ────────────────────────────────────────

    def record_audio(
        self,
        max_duration: float = 8.0,
        silence_timeout: float = 2.0,
        silence_threshold: float = 0.01,
    ) -> Optional[np.ndarray]:
        """
        Record audio with voice-activity detection.
        Stops after silence_timeout seconds of silence after speech starts.
        Returns numpy float32 array, or None if nothing was captured.
        """
        import sounddevice as sd

        logger.info('🎤 Listening for command...')
        frames = []
        silence_start  = None
        speech_started = False

        def callback(indata, frame_count, time_info, status):
            nonlocal silence_start, speech_started
            amplitude = float(np.abs(indata).mean())
            frames.append(indata.copy())
            if amplitude > silence_threshold:
                speech_started = True
                silence_start  = None
            elif speech_started and silence_start is None:
                silence_start = time.time()

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype='float32',
            callback=callback,
        ):
            start = time.time()
            while True:
                time.sleep(0.05)
                if time.time() - start >= max_duration:
                    break
                if speech_started and silence_start:
                    if time.time() - silence_start >= silence_timeout:
                        break

        if not frames:
            return None

        audio = np.concatenate(frames, axis=0).flatten()
        # Require at least 0.5s of audio
        if len(audio) < self.sample_rate * 0.5:
            return None

        logger.debug(f'Recorded {len(audio)/self.sample_rate:.1f}s of audio.')
        return audio

    # ── Transcription ──────────────────────────────────────────

    def transcribe(self, audio: np.ndarray) -> str:
        """
        Transcribe a numpy audio array using Whisper.
        Falls back to Google STT if Whisper unavailable.
        """
        model = self._load_model()

        if model == 'google_fallback':
            return self._google_transcribe(audio)

        try:
            # Whisper expects float32 mono at 16kHz
            result = model.transcribe(audio, fp16=False, language='en')
            text   = result.get('text', '').strip()
            logger.info(f'Transcribed: "{text}"')
            return text
        except Exception as e:
            logger.error(f'Whisper error: {e}. Falling back to Google STT.')
            return self._google_transcribe(audio)

    def _google_transcribe(self, audio: np.ndarray) -> str:
        """Fallback transcription using Google Speech Recognition."""
        import speech_recognition as sr
        try:
            audio_int16 = (audio * 32767).astype(np.int16).tobytes()
            recognizer  = sr.Recognizer()
            audio_data  = sr.AudioData(audio_int16, self.sample_rate, 2)
            text        = recognizer.recognize_google(audio_data)
            logger.info(f'Google STT: "{text}"')
            return text
        except Exception as e:
            logger.error(f'Google STT failed: {e}')
            return ''

    # ── Convenience: One-shot listen + transcribe ──────────────

    def listen_and_transcribe(self, max_duration: float = 8.0) -> str:
        """Record then transcribe in one call. Returns transcribed text."""
        audio = self.record_audio(max_duration=max_duration)
        if audio is None:
            return ''
        return self.transcribe(audio)
