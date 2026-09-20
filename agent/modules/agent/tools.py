"""
J.A.R.V.I.S. — Automation Tools
Custom LangChain tools that JARVIS can call autonomously.

Tools:
  1. execute_python   — Run Python code on the local machine
  2. web_scraper      — Fetch and summarise a web page
  3. file_manager     — Read, write, list files on disk
  4. system_command   — Open apps or run shell commands
  5. web_search       — Search Google (via scraping DuckDuckGo)
  6. save_memory      — Store a fact in long-term memory
  7. recall_memory    — Retrieve relevant memories
"""

import logging
import os
import platform
import subprocess
import sys
import textwrap
import traceback
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING

try:
    from langchain_core.tools import Tool
except ImportError:
    from langchain.tools import Tool

if TYPE_CHECKING:
    from modules.memory.memory_manager import MemoryManager

logger = logging.getLogger('jarvis.tools')


# ══════════════════════════════════════════════════════════════
#  TOOL 1: ExecutePython
# ══════════════════════════════════════════════════════════════

def execute_python(code: str) -> str:
    """
    Execute Python code safely and return its stdout output.
    JARVIS uses this to run automation scripts, calculations, data tasks.
    """
    logger.info(f'ExecutePython: running code ({len(code)} chars)')
    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = captured = StringIO()
    result = ''
    try:
        # Dedent in case the LLM added unnecessary indentation
        exec(textwrap.dedent(code), {'__name__': '__main__'})  # noqa: S102
        result = captured.getvalue().strip()
        if not result:
            result = '[Code executed successfully — no output produced.]'
    except Exception:
        result = f'[Error during execution]:\n{traceback.format_exc()}'
    finally:
        sys.stdout = old_stdout

    logger.info(f'ExecutePython result: {result[:200]}')
    return result[:4000]  # cap output length


# ══════════════════════════════════════════════════════════════
#  TOOL 2: WebScraper
# ══════════════════════════════════════════════════════════════

def web_scraper(url: str) -> str:
    """
    Fetch the text content of a URL and return a clean summary.
    JARVIS uses this to read articles, documentation, or any web page.
    """
    import requests
    from bs4 import BeautifulSoup

    logger.info(f'WebScraper: fetching {url}')
    try:
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 Chrome/120.0 Safari/537.36'
            )
        }
        resp = requests.get(url, headers=headers, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        # Remove noise
        for tag in soup(['script', 'style', 'nav', 'footer', 'header',
                         'aside', 'form', 'button', 'iframe']):
            tag.decompose()

        text = soup.get_text(separator='\n', strip=True)
        # Collapse blank lines
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        content = '\n'.join(lines)

        # Return up to 3000 chars
        if len(content) > 3000:
            content = content[:3000] + '\n\n[Content truncated. Ask for more if needed.]'

        logger.info(f'WebScraper: returned {len(content)} chars from {url}')
        return content

    except requests.exceptions.HTTPError as e:
        return f'[HTTP Error] {e}'
    except Exception as e:
        logger.error(f'WebScraper error: {e}')
        return f'[Scraping failed]: {str(e)}'


# ══════════════════════════════════════════════════════════════
#  TOOL 3: FileSystemManager
# ══════════════════════════════════════════════════════════════

def file_manager(command: str) -> str:
    """
    Manage files on the local system.

    Command format examples:
      read:/path/to/file.txt
      write:/path/to/file.txt|Content to write here
      list:/path/to/directory
      search:/directory|*.py
      exists:/path/to/file.txt
      delete:/path/to/file.txt

    Returns the result as a string.
    """
    command = command.strip()
    logger.info(f'FileManager: {command[:80]}')

    try:
        if command.startswith('read:'):
            path = Path(command[5:].strip())
            if not path.exists():
                return f'[File not found]: {path}'
            return path.read_text(encoding='utf-8', errors='replace')[:5000]

        elif command.startswith('write:'):
            parts = command[6:].split('|', 1)
            if len(parts) < 2:
                return '[Error]: write format is write:/path|content'
            path, content = Path(parts[0].strip()), parts[1]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
            return f'[Written successfully]: {path} ({len(content)} chars)'

        elif command.startswith('list:'):
            path = Path(command[5:].strip())
            if not path.exists():
                return f'[Directory not found]: {path}'
            items = sorted(path.iterdir())
            lines = [f'{"[DIR] " if p.is_dir() else "      "}{p.name}' for p in items[:50]]
            return f'Contents of {path}:\n' + '\n'.join(lines)

        elif command.startswith('search:'):
            parts = command[7:].split('|', 1)
            base  = Path(parts[0].strip())
            pattern = parts[1].strip() if len(parts) > 1 else '*'
            matches = list(base.rglob(pattern))[:30]
            return f'Found {len(matches)} matches:\n' + '\n'.join(str(m) for m in matches)

        elif command.startswith('exists:'):
            path = Path(command[7:].strip())
            return f'{path} — {"exists" if path.exists() else "does not exist"}'

        elif command.startswith('delete:'):
            path = Path(command[7:].strip())
            if not path.exists():
                return f'[File not found]: {path}'
            path.unlink()
            return f'[Deleted]: {path}'

        else:
            return (
                '[Unknown command]. Supported: '
                'read:/path | write:/path|content | list:/dir | '
                'search:/dir|pattern | exists:/path | delete:/path'
            )

    except PermissionError:
        return f'[Permission denied]: Cannot access that path.'
    except Exception as e:
        logger.error(f'FileManager error: {e}')
        return f'[FileManager error]: {str(e)}'


# ══════════════════════════════════════════════════════════════
#  TOOL 4: SystemCommands
# ══════════════════════════════════════════════════════════════

# Known application shortcuts for common requests
APP_MAP = {
    'spotify':   {'win': 'start spotify:', 'mac': 'open -a Spotify', 'linux': 'spotify'},
    'vscode':    {'win': 'code',           'mac': 'open -a "Visual Studio Code"', 'linux': 'code'},
    'vs code':   {'win': 'code',           'mac': 'open -a "Visual Studio Code"', 'linux': 'code'},
    'chrome':    {'win': 'start chrome',   'mac': 'open -a "Google Chrome"', 'linux': 'google-chrome'},
    'notepad':   {'win': 'notepad',        'mac': 'open -a TextEdit', 'linux': 'gedit'},
    'terminal':  {'win': 'start cmd',      'mac': 'open -a Terminal', 'linux': 'x-terminal-emulator'},
    'powershell':{'win': 'start powershell','mac': 'open -a Terminal', 'linux': 'x-terminal-emulator'},
    'calculator':{'win': 'calc',           'mac': 'open -a Calculator', 'linux': 'gnome-calculator'},
    'explorer':  {'win': 'explorer .',     'mac': 'open .', 'linux': 'nautilus .'},
    'brave':     {'win': 'start brave',    'mac': 'open -a Brave', 'linux': 'brave-browser'},
    'discord':   {'win': 'start discord:', 'mac': 'open -a Discord', 'linux': 'discord'},
    'youtube':   {'win': 'start https://youtube.com', 'mac': 'open https://youtube.com', 'linux': 'xdg-open https://youtube.com'},
}


def system_command(command: str) -> str:
    """
    Execute a system command or open an application.

    Command format examples:
      open:spotify
      open:vscode
      run:ipconfig
      run:dir C:\\Users
      open:https://youtube.com

    Returns the command output or status.
    """
    command = command.strip()
    logger.info(f'SystemCommand: {command}')
    os_name = platform.system().lower()
    os_key  = 'win' if os_name == 'windows' else ('mac' if os_name == 'darwin' else 'linux')

    try:
        # Open a known application
        if command.lower().startswith('open:'):
            target = command[5:].strip().lower()

            # URL
            if target.startswith('http'):
                if os_key == 'win':
                    os.startfile(target)
                elif os_key == 'mac':
                    subprocess.Popen(['open', target])
                else:
                    subprocess.Popen(['xdg-open', target])
                return f'[Opened in browser]: {target}'

            # Known app
            if target in APP_MAP:
                cmd = APP_MAP[target][os_key]
                if os_key == 'win':
                    os.system(cmd)
                else:
                    subprocess.Popen(cmd.split())
                return f'[Launched]: {target}'

            # Try directly
            if os_key == 'win':
                os.system(f'start {target}')
            else:
                subprocess.Popen([target])
            return f'[Attempted to launch]: {target}'

        # Run a shell command and capture output
        elif command.lower().startswith('run:'):
            cmd = command[4:].strip()
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout.strip() or result.stderr.strip() or '[No output]'
            return output[:3000]

        else:
            return '[Unknown format]. Use open:<app/url> or run:<shell command>'

    except subprocess.TimeoutExpired:
        return '[Error]: Command timed out after 30 seconds.'
    except Exception as e:
        logger.error(f'SystemCommand error: {e}')
        return f'[SystemCommand error]: {str(e)}'


# ══════════════════════════════════════════════════════════════
#  TOOL 5: WebSearch
# ══════════════════════════════════════════════════════════════

def web_search(query: str) -> str:
    """
    Search the web for a query using DuckDuckGo API and Wikipedia.
    Returns structured summaries and topic details.
    """
    import re
    import requests

    logger.info(f'WebSearch: "{query}"')
    results = []

    # 1. DuckDuckGo Instant Answer API (fast, reliable, unblocked)
    try:
        ddg_url = 'https://api.duckduckgo.com/'
        params = {'q': query, 'format': 'json', 'no_html': '1', 'skip_disambig': '1'}
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        resp = requests.get(ddg_url, params=params, headers=headers, timeout=8)
        data = resp.json()

        if data.get('AbstractText'):
            results.append(f"Summary: {data['AbstractText']}")
            if data.get('AbstractURL'):
                results.append(f"Source: {data['AbstractURL']}")

        for topic in data.get('RelatedTopics', [])[:4]:
            if isinstance(topic, dict) and topic.get('Text'):
                results.append(f"• {topic['Text']}")
    except Exception as e:
        logger.warning(f'DuckDuckGo API error: {e}')

    # 2. Wikipedia Search API (comprehensive knowledge fallback)
    if len(results) < 2:
        try:
            wiki_url = 'https://en.wikipedia.org/w/api.php'
            params = {
                'action': 'query',
                'list': 'search',
                'srsearch': query,
                'format': 'json',
                'utf8': 1,
            }
            headers = {'User-Agent': 'JarvisAssistant/1.0'}
            resp = requests.get(wiki_url, params=params, headers=headers, timeout=8)
            items = resp.json().get('query', {}).get('search', [])[:4]
            for item in items:
                clean_snippet = re.sub(r'<[^<]+?>', '', item.get('snippet', ''))
                results.append(f"• {item.get('title')}: {clean_snippet}")
        except Exception as e:
            logger.warning(f'Wikipedia search error: {e}')

    if results:
        return f'Search results for "{query}":\n\n' + '\n'.join(results)
    return f'[No results found for]: {query}'


# ══════════════════════════════════════════════════════════════
#  TOOL 6 & 7: Memory Tools (injected with memory instance)
# ══════════════════════════════════════════════════════════════

def make_save_memory_tool(memory: 'MemoryManager'):
    def save_memory(text: str) -> str:
        """Save an important fact or user preference to long-term memory."""
        # Check if it's a key=value preference
        if '=' in text and not text.startswith('{'):
            key, _, val = text.partition('=')
            memory.set(key.strip(), val.strip())
            memory.remember(text, category='preference')
            return f'[Saved preference]: {key.strip()} = {val.strip()}'
        else:
            memory.remember(text, category='fact')
            return f'[Stored in memory]: "{text[:60]}"'
    return save_memory


def make_recall_memory_tool(memory: 'MemoryManager'):
    def recall_memory(query: str) -> str:
        """Search long-term memory for relevant information."""
        results = memory.recall(query, n=5)
        prefs   = memory.all_preferences()
        parts   = []
        if prefs:
            parts.append('Preferences: ' + '; '.join(f'{k}={v}' for k, v in prefs.items()))
        if results:
            parts.append('Memories:\n' + '\n'.join(f'  • {r}' for r in results))
        return '\n'.join(parts) if parts else '[No relevant memories found.]'
    return recall_memory


# ══════════════════════════════════════════════════════════════
#  TOOL FACTORY — returns list of LangChain Tool objects
# ══════════════════════════════════════════════════════════════

def build_tools(memory: 'MemoryManager') -> list:
    """Build and return all LangChain Tool objects for the agent."""
    return [
        Tool(
            name='execute_python',
            func=execute_python,
            description=(
                'Execute Python code on the local machine and return output. '
                'Use for calculations, data processing, automation scripts, file operations. '
                'Input: a string of valid Python code.'
            ),
        ),
        Tool(
            name='web_scraper',
            func=web_scraper,
            description=(
                'Fetch and extract the text content of any web page URL. '
                'Use to read articles, documentation, or any website. '
                'Input: a full URL (e.g. https://example.com).'
            ),
        ),
        Tool(
            name='file_manager',
            func=file_manager,
            description=(
                'Read, write, list, search, or delete files on the local drive. '
                'Commands: read:/path | write:/path|content | list:/dir | '
                'search:/dir|pattern | exists:/path | delete:/path'
            ),
        ),
        Tool(
            name='system_command',
            func=system_command,
            description=(
                'Open applications or run shell commands on the local system. '
                'Commands: open:<app_name> (e.g. open:spotify, open:vscode) '
                'or run:<shell_command> (e.g. run:ipconfig).'
            ),
        ),
        Tool(
            name='web_search',
            func=web_search,
            description=(
                'Search the web for current information using DuckDuckGo. '
                'Use for news, facts, or anything requiring up-to-date information. '
                'Input: a natural language search query.'
            ),
        ),
        Tool(
            name='save_memory',
            func=make_save_memory_tool(memory),
            description=(
                'Save an important fact or user preference to long-term memory. '
                'Use this when the user shares personal information, preferences, or important facts. '
                'For preferences use format: key=value. For facts, write a plain sentence.'
            ),
        ),
        Tool(
            name='recall_memory',
            func=make_recall_memory_tool(memory),
            description=(
                'Search long-term memory for relevant stored information, preferences, or facts. '
                'Use before answering personal questions or when context from past sessions is needed. '
                'Input: a query describing what you are looking for.'
            ),
        ),
    ]
