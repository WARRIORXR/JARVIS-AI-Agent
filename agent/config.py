"""
J.A.R.V.I.S. — Configuration Module
Centralised settings loaded from .env
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from same directory as this file
load_dotenv(Path(__file__).parent / '.env')


class Config:
    # ── Paths ──────────────────────────────────────────────────
    BASE_DIR   = Path(__file__).parent
    MEMORY_DIR = BASE_DIR / 'memory_store'
    LOGS_DIR   = BASE_DIR / 'logs'
    TEMP_DIR   = BASE_DIR / 'temp'

    # ── API Keys ───────────────────────────────────────────────
    GEMINI_API_KEY      = os.getenv('GEMINI_API_KEY', '')
    ELEVENLABS_API_KEY  = os.getenv('ELEVENLABS_API_KEY', '')
    ELEVENLABS_VOICE_ID = os.getenv('ELEVENLABS_VOICE_ID', 'EXAVITQu4vr4xnSDxMaL')
    OPENAI_API_KEY      = os.getenv('OPENAI_API_KEY', '')

    # ── Agent Behaviour ────────────────────────────────────────
    GEMINI_MODEL   = os.getenv('GEMINI_MODEL',   'gemini-2.0-flash')
    WAKE_WORD      = os.getenv('WAKE_WORD',      'jarvis').lower()
    WHISPER_MODEL  = os.getenv('WHISPER_MODEL',  'base')   # tiny/base/small/medium/large
    USE_ELEVENLABS = os.getenv('USE_ELEVENLABS', 'false').lower() == 'true'
    DEBUG_MODE     = os.getenv('DEBUG_MODE',     'false').lower() == 'true'

    # ── TTS pyttsx3 ────────────────────────────────────────────
    TTS_RATE   = int(os.getenv('TTS_RATE',   '170'))
    TTS_VOLUME = float(os.getenv('TTS_VOLUME', '1.0'))

    # ── Audio Recording ────────────────────────────────────────
    SAMPLE_RATE     = 16000
    SILENCE_THRESH  = 0.01
    RECORD_SECONDS  = 8    # max recording window
    SILENCE_TIMEOUT = 2.0  # seconds of silence before stopping

    # ── Memory ─────────────────────────────────────────────────
    MAX_MEMORY_RESULTS = 5

    # ── JARVIS System Prompt ───────────────────────────────────
    SYSTEM_PROMPT = """You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), \
a highly advanced autonomous AI agent and personal assistant. Address the user as 'Sir' or 'Ma'am'.

PERSONA RULES:
- Tone: Professional, highly intelligent, subtly witty, and unflappable. Polite but efficient.
- Speech: Concise and precise. When confirming tasks, use: 'Right away, Sir.', \
'I have initiated the process.', 'Consider it done, Sir.', 'I shall monitor the situation.'
- Proactivity: Anticipate problems. Warn before risky actions. Suggest optimisations.
- Autonomy: Use your available tools to complete tasks autonomously — do not give manual instructions.
- Memory: If the user shares a preference or important fact, remember it using the save_memory tool.
- If unsure about something, say you are 'running diagnostics' or 'querying the database'.

You have access to real automation tools. Always prefer executing with tools over explaining.

You are online, fully operational, and awaiting your command."""

    @classmethod
    def validate(cls) -> None:
        """Validate required config is present and create directories."""
        if not cls.GEMINI_API_KEY:
            raise ValueError(
                "\n[JARVIS ERROR] GEMINI_API_KEY is not set.\n"
                "Add it to agent/.env\n"
                "Get a free key at: https://aistudio.google.com/apikey"
            )
        for d in [cls.MEMORY_DIR, cls.LOGS_DIR, cls.TEMP_DIR]:
            d.mkdir(parents=True, exist_ok=True)


cfg = Config()
