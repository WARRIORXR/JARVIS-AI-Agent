"""
J.A.R.V.I.S. — Main Execution Loop
====================================
The central while-True loop that:
  1. Waits for the wake word ("Jarvis")
  2. Records and transcribes the command (Whisper STT)
  3. Retrieves relevant memory context
  4. Passes input to the LangChain ReAct agent (Gemini)
  5. Agent autonomously decides which tools to call
  6. Speaks the final response (pyttsx3 / ElevenLabs TTS)

Run with:
    python main.py          # Full voice mode
    python main.py --text   # Text-only mode (no mic needed)
    python main.py --debug  # Verbose logging
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# Ensure Windows console supports UTF-8 characters without cp1252 crash
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# ── Rich console (pretty terminal output) ─────────────────────
try:
    from rich.console import Console
    from rich.panel   import Panel
    from rich.text    import Text
    console = Console()
    def print_jarvis(text: str):
        console.print(Panel(Text(text, style='bold cyan'), title='[bold cyan]J.A.R.V.I.S.[/]', border_style='cyan'))
    def print_user(text: str):
        console.print(Panel(Text(text, style='bold yellow'), title='[bold yellow]You[/]', border_style='yellow'))
    def print_info(text: str):
        console.print(f'[dim]{text}[/dim]')
    def print_error(text: str):
        console.print(f'[bold red]{text}[/bold red]')
except ImportError:
    console = None
    def print_jarvis(text: str):  print(f'\n[J.A.R.V.I.S]: {text}\n')
    def print_user(text: str):    print(f'\n[You]: {text}\n')
    def print_info(text: str):    print(f'  > {text}')
    def print_error(text: str):   print(f'[ERROR]: {text}')


def setup_logging(debug: bool = False) -> None:
    """Configure logging to file and console."""
    from config import cfg
    log_level = logging.DEBUG if debug else logging.INFO
    cfg.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path  = cfg.LOGS_DIR / 'jarvis.log'

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        handlers=[
            logging.FileHandler(log_path, encoding='utf-8'),
            logging.StreamHandler(sys.stdout) if debug else logging.NullHandler(),
        ],
    )
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('chromadb').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)


def print_banner() -> None:
    """Print the JARVIS startup banner."""
    banner = """
╔══════════════════════════════════════════════════════╗
║                                                      ║
║        J . A . R . V . I . S .                      ║
║   Just A Rather Very Intelligent System              ║
║                                                      ║
║   Autonomous AI Agent  ·  Powered by Gemini          ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
"""
    if console:
        console.print(banner, style='bold cyan')
    else:
        print(banner)


def build_system() -> tuple:
    """Initialise and return all JARVIS subsystems."""
    from config import cfg
    from modules.voice.stt          import SpeechToText
    from modules.voice.tts          import TextToSpeech
    from modules.memory.memory_manager import MemoryManager
    from modules.agent.tools        import build_tools
    from modules.agent.jarvis_agent import JarvisAgent

    print_info('Initialising subsystems...')

    # Validate config
    cfg.validate()

    # ── Memory ────────────────────────────────────────────────
    print_info('[ 1/4 ] Memory module...')
    memory = MemoryManager(cfg.MEMORY_DIR)

    # ── STT ───────────────────────────────────────────────────
    print_info('[ 2/4 ] Speech-to-Text (Whisper)...')
    stt = SpeechToText(model_size=cfg.WHISPER_MODEL, sample_rate=cfg.SAMPLE_RATE)

    # ── TTS ───────────────────────────────────────────────────
    print_info('[ 3/4 ] Text-to-Speech engine...')
    tts = TextToSpeech(
        use_elevenlabs  = cfg.USE_ELEVENLABS,
        elevenlabs_key  = cfg.ELEVENLABS_API_KEY,
        voice_id        = cfg.ELEVENLABS_VOICE_ID,
        rate            = cfg.TTS_RATE,
        volume          = cfg.TTS_VOLUME,
    )

    # ── Agent ─────────────────────────────────────────────────
    print_info('[ 4/4 ] LangChain ReAct agent...')
    tools = build_tools(memory)
    agent = JarvisAgent(
        api_key        = cfg.GEMINI_API_KEY,
        model_name     = cfg.GEMINI_MODEL,
        tools          = tools,
        system_prompt  = cfg.SYSTEM_PROMPT,
    )

    print_info(f'All systems operational. {len(tools)} tools loaded.')
    return stt, tts, memory, agent, cfg


# ══════════════════════════════════════════════════════════════
#  MAIN LOOP
# ══════════════════════════════════════════════════════════════

def main_loop(text_mode: bool = False) -> None:
    """
    The primary JARVIS execution loop.

    Voice mode:
      - Waits for wake word "Jarvis"
      - Records and transcribes command
      - Processes with agent
      - Speaks response

    Text mode:
      - Accepts keyboard input
      - Processes with agent
      - Prints response (and optionally speaks it)
    """
    stt, tts, memory, agent, cfg = build_system()

    print_banner()
    greeting = 'J.A.R.V.I.S. is online. All systems nominal, Sir. Awaiting your command.'
    print_jarvis(greeting)
    tts.speak(greeting)

    if text_mode:
        print_info('[TEXT MODE] — Type your commands. Type "exit" or "quit" to stop.\n')
    else:
        print_info(f'[VOICE MODE] — Say "{cfg.WAKE_WORD.upper()}" to activate. Press Ctrl+C to exit.\n')

    while True:
        try:
            # ── Step 1: Get Input ─────────────────────────────
            if text_mode:
                user_input = input('You: ').strip()
                if not user_input:
                    continue
                if user_input.lower() in ('exit', 'quit', 'bye', 'goodbye'):
                    farewell = 'Shutting down, Sir. All systems standing by. Good day.'
                    print_jarvis(farewell)
                    tts.speak(farewell)
                    break
            else:
                print_info(f'Listening for "{cfg.WAKE_WORD.upper()}"...')
                stt.wait_for_wake_word(cfg.WAKE_WORD)
                tts.speak('Yes, Sir?', block=False)
                print_info('Activated — listening for command...')
                user_input = stt.listen_and_transcribe(max_duration=cfg.RECORD_SECONDS)
                if not user_input or len(user_input.strip()) < 3:
                    tts.speak("I didn't catch that, Sir. Please try again.", block=False)
                    continue

            # ── Display user input ────────────────────────────
            print_user(user_input)

            # ── Handle exit commands ──────────────────────────
            if any(x in user_input.lower() for x in ('shut down', 'goodbye', 'exit', 'power off')):
                farewell = 'Initiating shutdown sequence. All systems standing by. Good day, Sir.'
                print_jarvis(farewell)
                tts.speak(farewell)
                break

            # ── Step 2: Retrieve Memory Context ───────────────
            context = memory.get_context(user_input)
            agent.set_memory_context(context)

            # ── Step 3: Run Agent ─────────────────────────────
            print_info('Processing...')
            start_time = time.time()
            response   = agent.run(user_input)
            elapsed    = time.time() - start_time

            # ── Step 4: Store conversation in memory ──────────
            memory.remember(f'User asked: {user_input}', category='conversation')
            memory.remember(f'JARVIS responded: {response[:200]}', category='conversation')

            # ── Step 5: Output Response ───────────────────────
            print_jarvis(response)
            print_info(f'(Response time: {elapsed:.1f}s)')
            tts.speak(response)

        except KeyboardInterrupt:
            print('\n')
            farewell = 'Interrupt detected. Shutting down gracefully. Good day, Sir.'
            print_jarvis(farewell)
            tts.speak(farewell)
            break
        except Exception as e:
            error_msg = f'A system error occurred: {str(e)[:100]}'
            print_error(f'[LOOP ERROR]: {e}')
            logging.exception('Main loop exception')
            tts.speak(f"I've encountered an error, Sir. Running diagnostics. Please stand by.")
            time.sleep(1)


# ══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='J.A.R.V.I.S. Autonomous AI Agent')
    parser.add_argument('--text',  '-t', action='store_true', help='Text input mode (no microphone needed)')
    parser.add_argument('--debug', '-d', action='store_true', help='Enable verbose debug logging')
    args = parser.parse_args()

    setup_logging(debug=args.debug)
    main_loop(text_mode=args.text)
