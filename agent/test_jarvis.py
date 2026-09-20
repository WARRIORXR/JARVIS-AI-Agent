"""
J.A.R.V.I.S. — Full Diagnostic Test Suite
==========================================
Tests every module, every tool, and the live AI connection.
Run: .\\venv\\Scripts\\python test_jarvis.py
"""

import sys
import os
import ast
import traceback
import time
from pathlib import Path

# Ensure Windows stdout/stderr supports UTF-8
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

sys.path.insert(0, str(Path(__file__).parent))

# ── Rich for pretty output ─────────────────────────────────────
try:
    from rich.console import Console
    from rich.table   import Table
    from rich.panel   import Panel
    from rich import box
    console = Console()
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    console = None

PASS  = '✅ PASS'
FAIL  = '❌ FAIL'
WARN  = '⚠️  WARN'
SKIP  = '⏭️  SKIP'

results = []   # (category, test_name, status, detail)

def record(category, name, status, detail=''):
    results.append((category, name, status, detail))
    sym = {'✅ PASS': '[green]PASS[/green]',
           '❌ FAIL': '[red]FAIL[/red]',
           '⚠️  WARN': '[yellow]WARN[/yellow]',
           '⏭️  SKIP': '[dim]SKIP[/dim]'}.get(status, status)
    if HAS_RICH:
        console.print(f'  {sym}  {name}' + (f' — [dim]{detail}[/dim]' if detail else ''))
    else:
        print(f'  {status}  {name}' + (f' — {detail}' if detail else ''))

def section(title):
    if HAS_RICH:
        console.print(f'\n[bold cyan]━━ {title} ━━[/bold cyan]')
    else:
        print(f'\n── {title} ──')


# ══════════════════════════════════════════════════════════════
#  1. FILE STRUCTURE CHECK
# ══════════════════════════════════════════════════════════════
section('FILE STRUCTURE')

REQUIRED_FILES = [
    '.env',
    'config.py',
    'main.py',
    'requirements.txt',
    'modules/__init__.py',
    'modules/voice/__init__.py',
    'modules/voice/stt.py',
    'modules/voice/tts.py',
    'modules/memory/__init__.py',
    'modules/memory/memory_manager.py',
    'modules/agent/__init__.py',
    'modules/agent/tools.py',
    'modules/agent/jarvis_agent.py',
]

base = Path(__file__).parent
for f in REQUIRED_FILES:
    p = base / f
    if p.exists() and p.stat().st_size > 0:
        record('files', f, PASS, f'{p.stat().st_size} bytes')
    elif p.exists():
        record('files', f, WARN, 'empty file')
    else:
        record('files', f, FAIL, 'MISSING')


# ══════════════════════════════════════════════════════════════
#  2. SYNTAX CHECK
# ══════════════════════════════════════════════════════════════
section('PYTHON SYNTAX CHECK')

PY_FILES = [
    'config.py', 'main.py',
    'modules/voice/stt.py', 'modules/voice/tts.py',
    'modules/memory/memory_manager.py',
    'modules/agent/tools.py', 'modules/agent/jarvis_agent.py',
]

for f in PY_FILES:
    p = base / f
    try:
        src = p.read_text(encoding='utf-8')
        ast.parse(src)
        record('syntax', f, PASS)
    except SyntaxError as e:
        record('syntax', f, FAIL, f'Line {e.lineno}: {e.msg}')
    except Exception as e:
        record('syntax', f, FAIL, str(e))


# ══════════════════════════════════════════════════════════════
#  3. PACKAGE IMPORTS
# ══════════════════════════════════════════════════════════════
section('PACKAGE IMPORTS')

PACKAGES = {
    'langchain':               'langchain',
    'langchain-google-genai':  'langchain_google_genai',
    'langchain-community':     'langchain_community',
    'google-generativeai':     'google.generativeai',
    'SpeechRecognition':       'speech_recognition',
    'pyttsx3':                 'pyttsx3',
    'requests':                'requests',
    'beautifulsoup4':          'bs4',
    'python-dotenv':           'dotenv',
    'rich':                    'rich',
    'colorama':                'colorama',
}

OPTIONAL_PACKAGES = {
    'openai-whisper': 'whisper',
    'sounddevice':    'sounddevice',
    'numpy':          'numpy',
    'chromadb':       'chromadb',
    'scipy':          'scipy',
    'pyaudio':        'pyaudio',
    'elevenlabs':     'elevenlabs',
}

for pkg_name, import_name in PACKAGES.items():
    try:
        mod = __import__(import_name)
        ver = getattr(mod, '__version__', '?')
        record('imports', pkg_name, PASS, f'v{ver}')
    except ImportError as e:
        record('imports', pkg_name, FAIL, 'Not installed — run: pip install ' + pkg_name)
    except Exception as e:
        record('imports', pkg_name, WARN, str(e)[:60])

for pkg_name, import_name in OPTIONAL_PACKAGES.items():
    try:
        mod = __import__(import_name)
        ver = getattr(mod, '__version__', '?')
        record('optional', pkg_name, PASS, f'v{ver}')
    except ImportError:
        record('optional', pkg_name, WARN, 'Optional — not installed (voice features may be limited)')
    except Exception as e:
        record('optional', pkg_name, WARN, str(e)[:60])


# ══════════════════════════════════════════════════════════════
#  4. CONFIG MODULE
# ══════════════════════════════════════════════════════════════
section('CONFIG MODULE')

try:
    from config import cfg
    record('config', 'config.py loads', PASS)
    record('config', 'GEMINI_MODEL set',   PASS if cfg.GEMINI_MODEL  else FAIL, cfg.GEMINI_MODEL)
    record('config', 'WAKE_WORD set',      PASS if cfg.WAKE_WORD     else FAIL, cfg.WAKE_WORD)
    record('config', 'WHISPER_MODEL set',  PASS if cfg.WHISPER_MODEL else FAIL, cfg.WHISPER_MODEL)
    record('config', 'SYSTEM_PROMPT set',  PASS if cfg.SYSTEM_PROMPT else FAIL, f'{len(cfg.SYSTEM_PROMPT)} chars')
    if cfg.GEMINI_API_KEY:
        masked = cfg.GEMINI_API_KEY[:6] + '...' + cfg.GEMINI_API_KEY[-4:]
        # Check key format
        if cfg.GEMINI_API_KEY.startswith('AIza'):
            record('config', 'GEMINI_API_KEY format', PASS, f'Valid format ({masked})')
        else:
            record('config', 'GEMINI_API_KEY format', WARN,
                   f'Key starts with "{cfg.GEMINI_API_KEY[:6]}" — expected "AIza". '
                   'Get a proper key from https://aistudio.google.com/apikey')
    else:
        record('config', 'GEMINI_API_KEY', FAIL, 'NOT SET — add to .env file')
except Exception as e:
    record('config', 'config.py loads', FAIL, str(e))


# ══════════════════════════════════════════════════════════════
#  5. MEMORY MODULE
# ══════════════════════════════════════════════════════════════
section('MEMORY MODULE')

try:
    from modules.memory.memory_manager import MemoryManager
    record('memory', 'MemoryManager imports', PASS)

    mem = MemoryManager(base / 'memory_store' / 'test')
    record('memory', 'MemoryManager init', PASS)

    # KV store
    mem.set('test_key', 'test_value_123')
    val = mem.get('test_key')
    if val == 'test_value_123':
        record('memory', 'KV set/get', PASS, 'Write and read verified')
    else:
        record('memory', 'KV set/get', FAIL, f'Expected "test_value_123", got "{val}"')

    prefs = mem.all_preferences()
    if 'test_key' in prefs:
        record('memory', 'KV persistence', PASS, f'{len(prefs)} key(s) stored')
    else:
        record('memory', 'KV persistence', FAIL, 'Key not found in preferences')

    # Vector memory
    if mem._col is not None:
        mem.remember('JARVIS test memory entry about Python programming', category='fact')
        results_vec = mem.recall('Python programming', n=3)
        if results_vec:
            record('memory', 'ChromaDB vector store', PASS, f'{mem.count()} vectors')
            record('memory', 'ChromaDB recall', PASS, f'Found {len(results_vec)} result(s)')
        else:
            record('memory', 'ChromaDB vector store', WARN, 'Stored but no recall results')
    else:
        record('memory', 'ChromaDB', WARN, 'Not available — install chromadb for long-term memory')

    # Context builder
    ctx = mem.get_context('test Python query')
    record('memory', 'Context builder', PASS, f'{len(ctx)} chars of context')

    # Cleanup test memory
    import shutil
    shutil.rmtree(base / 'memory_store' / 'test', ignore_errors=True)

except Exception as e:
    record('memory', 'Memory module', FAIL, str(e))
    traceback.print_exc()


# ══════════════════════════════════════════════════════════════
#  6. TOOLS MODULE
# ══════════════════════════════════════════════════════════════
section('TOOLS MODULE')

try:
    from modules.memory.memory_manager import MemoryManager
    from modules.agent.tools import (
        execute_python, web_scraper, file_manager,
        system_command, web_search, build_tools,
        make_save_memory_tool, make_recall_memory_tool,
    )
    record('tools', 'tools.py imports', PASS)

    mem_test = MemoryManager(base / 'memory_store' / 'test2')
    tools = build_tools(mem_test)
    record('tools', f'build_tools() returns {len(tools)} tools', PASS if len(tools) == 7 else FAIL,
           ', '.join(t.name for t in tools))

    # ── Tool 1: execute_python ─────────────────────────────────
    result = execute_python("x = 2 + 2\nprint(f'Result: {x}')")
    if 'Result: 4' in result:
        record('tools', 'execute_python', PASS, result.strip())
    else:
        record('tools', 'execute_python', FAIL, f'Got: {result}')

    # ── Tool 2: web_scraper ────────────────────────────────────
    try:
        scraped = web_scraper('https://httpbin.org/html')
        if scraped and len(scraped) > 50 and '[Scraping failed]' not in scraped:
            record('tools', 'web_scraper', PASS, f'{len(scraped)} chars scraped')
        elif '[Scraping failed]' in scraped or '[HTTP Error]' in scraped:
            record('tools', 'web_scraper', WARN, 'Network error (check internet connection)')
        else:
            record('tools', 'web_scraper', WARN, 'Short response — may be network issue')
    except Exception as e:
        record('tools', 'web_scraper', WARN, f'Network error: {str(e)[:50]}')

    # ── Tool 3: file_manager ───────────────────────────────────
    test_file = str(base / 'temp' / 'jarvis_test.txt')
    write_r = file_manager(f'write:{test_file}|Hello from J.A.R.V.I.S. test suite.')
    if '[Written' in write_r:
        record('tools', 'file_manager write', PASS, write_r[:60])
        read_r = file_manager(f'read:{test_file}')
        if 'Hello from J.A.R.V.I.S.' in read_r:
            record('tools', 'file_manager read', PASS, read_r[:50])
        else:
            record('tools', 'file_manager read', FAIL, f'Got: {read_r[:50]}')
        list_r = file_manager(f'list:{base / "temp"}')
        record('tools', 'file_manager list', PASS if 'jarvis_test' in list_r else WARN, list_r[:80])
        # Cleanup
        file_manager(f'delete:{test_file}')
    else:
        record('tools', 'file_manager write', FAIL, write_r[:80])

    # ── Tool 4: system_command ─────────────────────────────────
    cmd_r = system_command('run:echo JARVIS_TEST_OK')
    if 'JARVIS_TEST_OK' in cmd_r:
        record('tools', 'system_command run', PASS, cmd_r.strip())
    else:
        record('tools', 'system_command run', WARN, f'Got: {cmd_r[:60]}')

    # ── Tool 5: web_search ─────────────────────────────────────
    try:
        search_r = web_search('Python programming language')
        if search_r and 'Python' in search_r and 'Search results' in search_r:
            record('tools', 'web_search', PASS, f'{len(search_r)} chars')
        elif '[Search failed]' in search_r:
            record('tools', 'web_search', WARN, 'Network error — check internet')
        else:
            record('tools', 'web_search', WARN, f'Unexpected response: {search_r[:60]}')
    except Exception as e:
        record('tools', 'web_search', WARN, f'Network error: {str(e)[:50]}')

    # ── Tool 6 & 7: Memory tools ───────────────────────────────
    save_fn   = make_save_memory_tool(mem_test)
    recall_fn = make_recall_memory_tool(mem_test)
    save_r = save_fn('user_name=Tony Stark')
    if '[Saved preference]' in save_r or '[Stored' in save_r:
        record('tools', 'save_memory tool', PASS, save_r[:60])
    else:
        record('tools', 'save_memory tool', WARN, save_r[:60])
    recall_r = recall_fn('user name')
    record('tools', 'recall_memory tool', PASS if 'Tony' in recall_r or 'user_name' in recall_r else WARN,
           recall_r[:80])

    import shutil
    shutil.rmtree(base / 'memory_store' / 'test2', ignore_errors=True)

except Exception as e:
    record('tools', 'tools.py', FAIL, str(e))
    traceback.print_exc()


# ══════════════════════════════════════════════════════════════
#  7. TTS MODULE
# ══════════════════════════════════════════════════════════════
section('TTS MODULE')

try:
    from modules.voice.tts import TextToSpeech
    record('tts', 'tts.py imports', PASS)

    tts = TextToSpeech(use_elevenlabs=False, rate=200)
    record('tts', 'TextToSpeech init (pyttsx3)', PASS)

    # Test text cleaning
    dirty = '## Hello **world** `code` here\n\nNew paragraph.'
    cleaned = tts._clean(dirty)
    if '##' not in cleaned and '**' not in cleaned and '`' not in cleaned:
        record('tts', 'Markdown cleaner', PASS, f'Output: "{cleaned}"')
    else:
        record('tts', 'Markdown cleaner', WARN, f'Markdown not fully stripped: "{cleaned}"')

    # Try speaking (non-blocking)
    try:
        tts.speak('J.A.R.V.I.S. test suite complete.', block=False)
        time.sleep(0.5)
        record('tts', 'pyttsx3 speak (non-blocking)', PASS)
    except Exception as e:
        record('tts', 'pyttsx3 speak', WARN, f'Speaker may not be available: {str(e)[:60]}')

except Exception as e:
    record('tts', 'TTS module', FAIL, str(e))


# ══════════════════════════════════════════════════════════════
#  8. STT MODULE
# ══════════════════════════════════════════════════════════════
section('STT MODULE')

try:
    from modules.voice.stt import SpeechToText
    record('stt', 'stt.py imports', PASS)

    stt = SpeechToText(model_size='base')
    record('stt', 'SpeechToText init', PASS)

    # Check if sounddevice available
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        input_devs = [d for d in devices if d['max_input_channels'] > 0]
        if input_devs:
            record('stt', 'Audio input devices', PASS, f'{len(input_devs)} microphone(s) found')
        else:
            record('stt', 'Audio input devices', WARN, 'No microphone detected')
    except ImportError:
        record('stt', 'sounddevice', WARN, 'Not installed — install for local audio capture')
    except Exception as e:
        record('stt', 'Audio devices query', WARN, str(e)[:60])

    # Check Whisper
    try:
        import whisper
        record('stt', 'Whisper installed', PASS, f'v{getattr(whisper, "__version__", "?")}')
    except ImportError:
        record('stt', 'Whisper installed', WARN, 'Not installed — install openai-whisper for offline STT')

    # Check SpeechRecognition
    try:
        import speech_recognition as sr
        record('stt', 'SpeechRecognition', PASS, f'v{sr.__version__}')
    except ImportError:
        record('stt', 'SpeechRecognition', FAIL, 'Required — run: pip install SpeechRecognition')

except Exception as e:
    record('stt', 'STT module', FAIL, str(e))


# ══════════════════════════════════════════════════════════════
#  9. AGENT MODULE (without calling Gemini)
# ══════════════════════════════════════════════════════════════
section('AGENT MODULE')

try:
    from modules.agent.jarvis_agent import JarvisAgent, REACT_TEMPLATE
    record('agent', 'jarvis_agent.py imports', PASS)
    record('agent', 'REACT_TEMPLATE defined', PASS, f'{len(REACT_TEMPLATE)} chars')

    # Verify template has required placeholders
    required_vars = ['{system_prompt}', '{tools}', '{tool_names}', '{input}', '{agent_scratchpad}']
    missing = [v for v in required_vars if v not in REACT_TEMPLATE]
    if not missing:
        record('agent', 'Template placeholders', PASS, 'All required vars present')
    else:
        record('agent', 'Template placeholders', FAIL, f'Missing: {missing}')

    # Test LangChain imports
    try:
        from langchain.agents import create_react_agent, AgentExecutor
    except ImportError:
        from langchain_classic.agents import create_react_agent, AgentExecutor
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.prompts import PromptTemplate
    record('agent', 'LangChain core imports', PASS)
    record('agent', 'LangChain Google Genai', PASS)

except Exception as e:
    record('agent', 'Agent module', FAIL, str(e))
    traceback.print_exc()


# ══════════════════════════════════════════════════════════════
#  10. LIVE GEMINI API TEST
# ══════════════════════════════════════════════════════════════
section('LIVE GEMINI API TEST')

try:
    from config import cfg
    if not cfg.GEMINI_API_KEY:
        record('gemini', 'API key present', FAIL, 'Not set in .env')
    elif not cfg.GEMINI_API_KEY.startswith('AIza'):
        record('gemini', 'API key format', WARN,
               f'Key format looks wrong (starts with "{cfg.GEMINI_API_KEY[:6]}"). '
               'Should start with "AIza". Get key from https://aistudio.google.com/apikey')
        record('gemini', 'Live API call', SKIP, 'Skipped due to invalid key format')
    else:
        record('gemini', 'API key format', PASS, cfg.GEMINI_API_KEY[:6] + '...')

        # Test via LangChain (the way the agent uses it)
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage
        import os
        os.environ['GOOGLE_API_KEY'] = cfg.GEMINI_API_KEY

        llm = ChatGoogleGenerativeAI(
            model=cfg.GEMINI_MODEL,
            google_api_key=cfg.GEMINI_API_KEY,
            temperature=0.1,
        )
        t0  = time.time()
        msg = llm.invoke([HumanMessage(content='Reply with exactly 3 words: "JARVIS is operational"')])
        ms  = int((time.time() - t0) * 1000)
        reply = msg.content.strip()

        if reply:
            record('gemini', f'Live API call ({cfg.GEMINI_MODEL})', PASS, f'"{reply}" — {ms}ms')
        else:
            record('gemini', 'Live API call', WARN, 'Empty response')

except Exception as e:
    record('gemini', 'Live API call', FAIL, str(e)[:120])


# ══════════════════════════════════════════════════════════════
#  11. INTEGRATION TEST — Full agent run (if key is valid)
# ══════════════════════════════════════════════════════════════
section('INTEGRATION TEST')

try:
    from config import cfg
    if not cfg.GEMINI_API_KEY or not cfg.GEMINI_API_KEY.startswith('AIza'):
        record('integration', 'Full agent run', SKIP, 'Skipped — valid API key required')
    else:
        from modules.memory.memory_manager import MemoryManager
        from modules.agent.tools import build_tools
        from modules.agent.jarvis_agent import JarvisAgent

        mem_int = MemoryManager(base / 'memory_store' / 'test_int')
        tools   = build_tools(mem_int)
        agent   = JarvisAgent(
            api_key=cfg.GEMINI_API_KEY,
            model_name=cfg.GEMINI_MODEL,
            tools=tools,
            system_prompt=cfg.SYSTEM_PROMPT,
        )
        record('integration', 'JarvisAgent instantiated', PASS)

        # Run a tool-using query
        t0     = time.time()
        answer = agent.run('Use the execute_python tool to calculate 7 * 8 and tell me the result.')
        ms     = int((time.time() - t0) * 1000)

        if answer and len(answer) > 5:
            has_56 = '56' in answer
            record('integration', 'Agent tool-use test', PASS if has_56 else WARN,
                   f'Response ({ms}ms): "{answer[:100]}"')
        else:
            record('integration', 'Agent tool-use test', FAIL, f'Empty or too-short response: "{answer}"')

        import shutil
        shutil.rmtree(base / 'memory_store' / 'test_int', ignore_errors=True)

except Exception as e:
    record('integration', 'Integration test', FAIL, str(e)[:120])
    traceback.print_exc()


# ══════════════════════════════════════════════════════════════
#  FINAL REPORT
# ══════════════════════════════════════════════════════════════
total  = len(results)
passed = sum(1 for r in results if r[2] == PASS)
failed = sum(1 for r in results if r[2] == FAIL)
warned = sum(1 for r in results if r[2] == WARN)
skipped= sum(1 for r in results if r[2] == SKIP)

if HAS_RICH:
    console.print()
    console.print(Panel(
        f'[bold green]{passed} PASSED[/bold green]  '
        f'[bold red]{failed} FAILED[/bold red]  '
        f'[yellow]{warned} WARNINGS[/yellow]  '
        f'[dim]{skipped} SKIPPED[/dim]  '
        f'/ {total} total',
        title='[bold white]JARVIS DIAGNOSTIC REPORT[/bold white]',
        border_style='cyan',
    ))
    if failed > 0:
        console.print('\n[bold red]FAILURES:[/bold red]')
        for cat, name, status, detail in results:
            if status == FAIL:
                console.print(f'  ❌ [{cat}] {name}: [red]{detail}[/red]')
    if warned > 0:
        console.print('\n[yellow]WARNINGS:[/yellow]')
        for cat, name, status, detail in results:
            if status == WARN:
                console.print(f'  ⚠️  [{cat}] {name}: [yellow]{detail}[/yellow]')
    if failed == 0:
        console.print('\n[bold green]All critical tests passed! JARVIS is ready.[/bold green]')
        console.print('[dim]Run: .\\venv\\Scripts\\python main.py --text[/dim]')
    else:
        console.print(f'\n[bold red]{failed} critical issue(s) must be fixed before running JARVIS.[/bold red]')
else:
    print(f'\n=== REPORT: {passed} PASS | {failed} FAIL | {warned} WARN | {skipped} SKIP ===')
    for cat, name, status, detail in results:
        if status in (FAIL, WARN):
            print(f'  {status} [{cat}] {name}: {detail}')
