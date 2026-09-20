# J.A.R.V.I.S. — Autonomous AI Agent

> **Just A Rather Very Intelligent System** — A real local AI agent powered by Gemini, LangChain, Whisper, and custom automation tools.

> [!IMPORTANT]
> **You need a proper Gemini API key** to use the AI features.
> Get one FREE at **https://aistudio.google.com/apikey** (click "Create API key")
> The key should start with `AIza...`. Paste it into `.env` as `GEMINI_API_KEY=AIza...`

---

## Project Structure

```
agent/
├── main.py                          ← Main execution loop (start here)
├── config.py                        ← All settings (loads from .env)
├── .env                             ← Your API keys & config
├── requirements.txt                 ← Python dependencies
├── install.bat                      ← One-click installer (Windows)
├── run.bat                          ← Quick launcher
│
├── modules/
│   ├── voice/
│   │   ├── stt.py                   ← Speech-to-Text (Whisper + Google fallback)
│   │   └── tts.py                   ← Text-to-Speech (ElevenLabs + pyttsx3)
│   ├── memory/
│   │   └── memory_manager.py        ← ChromaDB vector DB + JSON preferences
│   └── agent/
│       ├── jarvis_agent.py          ← LangChain ReAct agent (Gemini)
│       └── tools.py                 ← 7 custom automation tools
│
├── memory_store/                    ← Auto-created: persistent memory
│   ├── chroma/                      ← ChromaDB vector database
│   └── preferences.json            ← User preferences & facts
└── logs/
    └── jarvis.log                   ← Full execution log
```

---

## Quick Start

### Step 1: Install dependencies
```batch
cd d:\ANTIGRAVITY\JARVIS\agent
install.bat
```

### Step 2: Configure API key
Edit `.env` — your Gemini key is already set. If you need a new one:
→ https://aistudio.google.com/apikey

### Step 3: Run JARVIS

**Text mode** (recommended for first run — no microphone needed):
```batch
run.bat --text
```

**Voice mode** (say "Jarvis" to activate):
```batch
run.bat
```

**Debug mode** (see everything that's happening):
```batch
run.bat --text --debug
```

---

## Available Tools

JARVIS autonomously decides when to use these tools:

| Tool | What it does |
|---|---|
| `execute_python` | Runs Python code on your machine and returns output |
| `web_scraper` | Fetches and reads any web page |
| `file_manager` | Read, write, list, search files on your drive |
| `system_command` | Opens apps (Spotify, VS Code, Chrome) or runs shell commands |
| `web_search` | Searches DuckDuckGo — no API key needed |
| `save_memory` | Stores facts/preferences to long-term memory |
| `recall_memory` | Retrieves relevant memories from previous sessions |

---

## Example Commands

Try these after launching:

```
You: What's the weather like in London today?
You: Open Spotify
You: Write a Python script to rename all jpg files in my Downloads folder
You: Read the file C:\Users\asus\Documents\notes.txt
You: Search for the latest news about AI
You: Remember that my name is [your name] and I prefer dark mode
You: What do you remember about me?
You: Run ipconfig and tell me my IP address
You: Summarise this webpage: https://en.wikipedia.org/wiki/Artificial_intelligence
```

---

## Voice Setup (Optional)

### Better voice quality — ElevenLabs
1. Get a free API key: https://elevenlabs.io
2. Edit `.env`:
   ```
   USE_ELEVENLABS=true
   ELEVENLABS_API_KEY=your_key_here
   ```

### Faster STT — Use smaller Whisper model
Edit `.env`:
```
WHISPER_MODEL=tiny   # fastest, less accurate
WHISPER_MODEL=base   # recommended (default)
WHISPER_MODEL=small  # more accurate, slower
```

---

## Architecture

```
Wake Word Detected
       │
       ▼
  STT (Whisper)
  transcribes command
       │
       ▼
 Memory Manager
 retrieves context
       │
       ▼
  LangChain ReAct Agent (Gemini)
  ┌─────────────────────────────┐
  │ Thought → Action → Tool     │
  │ Observation → Next Thought  │
  │ ... (up to 8 iterations)    │
  │ Final Answer                │
  └─────────────────────────────┘
       │
       ▼
  Memory Manager
  stores conversation
       │
       ▼
  TTS speaks response
       │
       ▼
  Back to listening...
```
