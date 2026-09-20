"""
J.A.R.V.I.S. — Text-to-Speech Module
Primary:  ElevenLabs API (high-quality, natural voice)
Fallback: pyttsx3 (offline, free)
"""

import io
import logging
import re
import threading
from typing import Optional

logger = logging.getLogger('jarvis.tts')


class TextToSpeech:
    """
    Dual-engine TTS: ElevenLabs (premium) with pyttsx3 offline fallback.
    """

    def __init__(
        self,
        use_elevenlabs:  bool  = False,
        elevenlabs_key:  str   = '',
        voice_id:        str   = 'EXAVITQu4vr4xnSDxMaL',  # ElevenLabs 'Bella'
        rate:            int   = 170,
        volume:          float = 1.0,
    ):
        self.use_elevenlabs = use_elevenlabs and bool(elevenlabs_key)
        self.elevenlabs_key = elevenlabs_key
        self.voice_id       = voice_id
        self.rate           = rate
        self.volume         = volume
        self._engine        = None
        self._lock          = threading.Lock()

        if self.use_elevenlabs:
            logger.info('TTS engine: ElevenLabs (high quality)')
        else:
            logger.info('TTS engine: pyttsx3 (offline)')
            self._init_pyttsx3()

    # ── pyttsx3 ───────────────────────────────────────────────

    def _init_pyttsx3(self) -> None:
        """Initialise the pyttsx3 offline TTS engine."""
        try:
            import pyttsx3
            self._engine = pyttsx3.init()
            self._engine.setProperty('rate',   self.rate)
            self._engine.setProperty('volume', self.volume)

            # Try to pick a clear male voice (David on Windows)
            voices = self._engine.getProperty('voices')
            preferred = ['david', 'mark', 'george', 'james']
            for voice in voices:
                if any(p in voice.name.lower() for p in preferred):
                    self._engine.setProperty('voice', voice.id)
                    logger.info(f'pyttsx3 voice: {voice.name}')
                    break

            logger.info(f'pyttsx3 ready — rate={self.rate} wpm')
        except Exception as e:
            logger.error(f'pyttsx3 init failed: {e}')
            self._engine = None

    # ── Public API ─────────────────────────────────────────────

    def speak(self, text: str, block: bool = True) -> None:
        """
        Speak text aloud.
        block=True: wait until speech finishes before returning.
        block=False: run in background thread.
        """
        if not text or not text.strip():
            return

        text = self._clean(text)
        preview = text[:70] + '...' if len(text) > 70 else text
        logger.info(f'Speaking: "{preview}"')

        fn = self._speak_elevenlabs if self.use_elevenlabs else self._speak_pyttsx3

        if block:
            fn(text)
        else:
            threading.Thread(target=fn, args=(text,), daemon=True).start()

    # ── ElevenLabs ─────────────────────────────────────────────

    def _speak_elevenlabs(self, text: str) -> None:
        """Stream and play audio from ElevenLabs API."""
        try:
            from elevenlabs import ElevenLabs, VoiceSettings
            import pygame

            client = ElevenLabs(api_key=self.elevenlabs_key)
            stream = client.text_to_speech.convert(
                voice_id=self.voice_id,
                text=text,
                model_id='eleven_turbo_v2',
                voice_settings=VoiceSettings(stability=0.5, similarity_boost=0.75),
            )
            audio = b''.join(stream)

            if not pygame.mixer.get_init():
                pygame.mixer.init()
            sound = pygame.mixer.Sound(io.BytesIO(audio))
            sound.play()
            while pygame.mixer.get_busy():
                pygame.time.wait(50)

        except ImportError:
            logger.warning('ElevenLabs not installed. Falling back to pyttsx3.')
            self._speak_pyttsx3(text)
        except Exception as e:
            logger.error(f'ElevenLabs error: {e}. Falling back to pyttsx3.')
            self._speak_pyttsx3(text)

    # ── pyttsx3 speak ─────────────────────────────────────────

    def _speak_pyttsx3(self, text: str) -> None:
        """Speak using pyttsx3 offline engine."""
        with self._lock:
            try:
                if self._engine is None:
                    self._init_pyttsx3()
                if self._engine:
                    self._engine.say(text)
                    self._engine.runAndWait()
                else:
                    # Last resort: print
                    print(f'\n[J.A.R.V.I.S]: {text}\n')
            except Exception as e:
                logger.error(f'pyttsx3 speak error: {e}')
                print(f'\n[J.A.R.V.I.S]: {text}\n')

    # ── Text Cleaning ──────────────────────────────────────────

    def _clean(self, text: str) -> str:
        """Strip markdown and code blocks before speaking."""
        # Remove code blocks entirely
        text = re.sub(r'```[\s\S]*?```', 'code block omitted.', text)
        # Remove inline code
        text = re.sub(r'`[^`]+`', '', text)
        # Bold/italic
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*',     r'\1', text)
        # Headers
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        # Links
        text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
        # Bullet points
        text = re.sub(r'^\s*[-•]\s+', '', text, flags=re.MULTILINE)
        # Multiple newlines to pause
        text = re.sub(r'\n{2,}', '. ', text)
        text = re.sub(r'\n', ' ', text)
        # Trim length for TTS (don't read 2000-word essays)
        if len(text) > 600:
            text = text[:600] + '... I have more detail available if you require it, Sir.'
        return text.strip()
