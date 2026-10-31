# J.A.R.V.I.S. — Rust Edition (text mode)

Terminal port of the Python JARVIS agent (`agent/` in the parent folder):
same persona, same ReAct loop over Gemini, same 7 tools, same
`preferences.json` KV memory format (it reads/writes the same shape).

## Run

```bash
cargo run
```

**Requires a valid `GEMINI_API_KEY` in this folder's `.env`.**
The key currently in `agent/.env` starts with `AQ.` — that's a placeholder/
expired key (the Python config itself rejects `AQ.` keys), so get a fresh one
at https://aistudio.google.com/apikey and paste it here.

## What's ported

| Python | Rust |
|---|---|
| LangChain `create_react_agent` loop | hand-rolled ReAct loop (same prompt, 8 iterations, `Observation:` stop sequence) |
| `tools.py` — execute_python, web_scraper, file_manager, system_command, web_search | all ported (`web_search` = DuckDuckGo Instant Answer API + Wikipedia fallback, same as Python) |
| save_memory / recall_memory | same `key = value` semantics, `memory_store/preferences.json` |
| ChromaDB vector recall | keyword recall over `memory_store/memories.json` |
| Whisper STT + pyttsx3/ElevenLabs TTS voice loop | **not ported** — no Rust equivalent; you type instead of speak |

Type `exit` or Ctrl+D to quit. Unit tests cover the ReAct parser and memory:
`cargo test`.
