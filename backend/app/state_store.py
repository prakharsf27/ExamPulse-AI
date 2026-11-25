from __future__ import annotations

import json
import logging
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional

from app.config import settings

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[1] / ".data"
SESSIONS_FILE = DATA_DIR / "sessions.json"


class StateStore:
    """Session state persistence backed by Supabase with automatic local JSON/in-memory fallback."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._memory: Dict[str, Dict[str, Any]] = {}
        self._supabase = None
        self._mode = "local"

        if settings.has_supabase:
            try:
                from supabase import create_client

                self._supabase = create_client(settings.supabase_url, settings.supabase_key)
                self._mode = "supabase"
            except Exception as exc:
                logger.warning("Supabase init failed (%s); using local fallback.", exc)
                self._supabase = None
                self._mode = "local"

        self._load_local_cache()

    @property
    def mode(self) -> str:
        return self._mode

    def _load_local_cache(self) -> None:
        try:
            if SESSIONS_FILE.exists():
                raw = SESSIONS_FILE.read_text(encoding="utf-8")
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    self._memory = parsed
        except Exception as exc:
            logger.warning("Could not load local session cache: %s", exc)

    def _persist_local_cache(self) -> None:
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            SESSIONS_FILE.write_text(json.dumps(self._memory, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("Could not persist local session cache: %s", exc)

    def save_session(self, session_id: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            self._memory[session_id] = payload
            self._persist_local_cache()

        if self._supabase is not None:
            try:
                self._supabase.table("exampulse_sessions").upsert(
                    {"session_id": session_id, "payload": payload}
                ).execute()
            except Exception as exc:
                logger.warning("Supabase upsert failed (%s); data retained locally.", exc)

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            if session_id in self._memory:
                return self._memory[session_id]

        if self._supabase is not None:
            try:
                res = (
                    self._supabase.table("exampulse_sessions")
                    .select("payload")
                    .eq("session_id", session_id)
                    .limit(1)
                    .execute()
                )
                if res.data:
                    payload = res.data[0].get("payload")
                    if isinstance(payload, dict):
                        with self._lock:
                            self._memory[session_id] = payload
                        return payload
            except Exception as exc:
                logger.warning("Supabase fetch failed (%s).", exc)
        return None


state_store = StateStore()
