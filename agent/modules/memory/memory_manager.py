"""
J.A.R.V.I.S. — Memory Manager
Dual-layer memory:
  1. Vector Memory  — ChromaDB semantic search (long-term recall)
  2. Key-Value Store — JSON file (preferences, facts, schedule)
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger('jarvis.memory')


class MemoryManager:
    """
    Manages JARVIS's memory across sessions.
    Vector memory uses ChromaDB for semantic similarity search.
    KV memory uses a JSON file for structured persistent data.
    """

    def __init__(self, memory_dir: Path):
        self.memory_dir  = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.kv_path     = self.memory_dir / 'preferences.json'
        self._kv         = self._load_kv()
        self._chroma     = None
        self._col        = None
        self._init_chroma()
        logger.info(f'Memory Manager ready. KV entries: {len(self._kv)}')

    # ══════════════════════════════════════════════════════════
    #  VECTOR MEMORY — ChromaDB
    # ══════════════════════════════════════════════════════════

    def _init_chroma(self) -> None:
        """Initialise ChromaDB persistent vector store."""
        try:
            import chromadb
            self._chroma = chromadb.PersistentClient(
                path=str(self.memory_dir / 'chroma')
            )
            self._col = self._chroma.get_or_create_collection(
                name='jarvis_memory',
                metadata={'hnsw:space': 'cosine'},
            )
            logger.info(f'ChromaDB ready — {self._col.count()} vectors stored.')
        except ImportError:
            logger.warning('chromadb not installed — long-term vector memory disabled.')
        except Exception as e:
            logger.error(f'ChromaDB init error: {e}')

    def remember(
        self,
        text:     str,
        category: str  = 'conversation',
        metadata: Dict = None,
    ) -> None:
        """
        Store a fact or conversation turn in vector memory.
        category: 'conversation' | 'fact' | 'preference' | 'task'
        """
        if not self._col:
            return
        try:
            doc_id = f'{category}_{int(time.time() * 1000)}'
            meta   = {
                'category':  category,
                'timestamp': datetime.now().isoformat(),
            }
            if metadata:
                meta.update(metadata)
            self._col.add(documents=[text], metadatas=[meta], ids=[doc_id])
            logger.debug(f'Stored [{category}]: "{text[:60]}"')
        except Exception as e:
            logger.error(f'Memory store error: {e}')

    def recall(
        self,
        query:    str,
        n:        int = 5,
        category: Optional[str] = None,
    ) -> List[str]:
        """
        Semantic search over stored memories.
        Returns list of relevant document strings.
        """
        if not self._col or self._col.count() == 0:
            return []
        try:
            kwargs = dict(
                query_texts=[query],
                n_results=min(n, self._col.count()),
            )
            if category:
                kwargs['where'] = {'category': category}
            results = self._col.query(**kwargs)
            docs = results.get('documents', [[]])[0]
            logger.debug(f'Recalled {len(docs)} memories for: "{query[:40]}"')
            return docs
        except Exception as e:
            logger.error(f'Memory recall error: {e}')
            return []

    def count(self) -> int:
        """Number of vectors in memory."""
        return self._col.count() if self._col else 0

    # ══════════════════════════════════════════════════════════
    #  KEY-VALUE MEMORY — JSON
    # ══════════════════════════════════════════════════════════

    def _load_kv(self) -> Dict:
        """Load KV store from disk."""
        if self.kv_path.exists():
            try:
                with open(self.kv_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_kv(self) -> None:
        """Persist KV store to disk."""
        with open(self.kv_path, 'w', encoding='utf-8') as f:
            json.dump(self._kv, f, indent=2, ensure_ascii=False)

    def set(self, key: str, value: Any) -> None:
        """Save a key-value preference or fact."""
        self._kv[key] = {'value': value, 'updated': datetime.now().isoformat()}
        self._save_kv()
        logger.info(f'KV set: {key} = {value}')

    def get(self, key: str, default: Any = None) -> Any:
        """Get a stored preference by key."""
        entry = self._kv.get(key)
        return entry['value'] if entry else default

    def all_preferences(self) -> Dict:
        """Return all preferences as a simple dict."""
        return {k: v['value'] for k, v in self._kv.items()}

    # ══════════════════════════════════════════════════════════
    #  CONTEXT BUILDER
    # ══════════════════════════════════════════════════════════

    def get_context(self, query: str) -> str:
        """
        Build a context string from relevant memories to prepend to LLM calls.
        """
        parts = []

        prefs = self.all_preferences()
        if prefs:
            pref_str = '; '.join(f'{k}={v}' for k, v in list(prefs.items())[:8])
            parts.append(f'[User Preferences]: {pref_str}')

        memories = self.recall(query, n=4)
        if memories:
            parts.append('[Relevant Memories]:')
            for i, m in enumerate(memories, 1):
                parts.append(f'  {i}. {m}')

        return '\n'.join(parts) if parts else ''
