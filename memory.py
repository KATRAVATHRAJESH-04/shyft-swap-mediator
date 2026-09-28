"""Thin wrapper around Hindsight: retain() and recall().

Set DEMO_MOCK=1 to use an in-memory fake instead (no keys needed).
Hindsight docs: https://hindsight.vectorize.io/sdks/python
"""
import os
import re
from datetime import datetime

from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def get_bank_id() -> str:
    """Read bank id: explicit test bank > .bank_id file > env var > default."""
    env_bank = os.getenv("HINDSIGHT_BANK_ID")
    if env_bank and ("test" in env_bank.lower() or os.getenv("HINDSIGHT_IGNORE_BANK_ID_FILE") == "1"):
        return env_bank

    bank_file = Path(__file__).resolve().parent / ".bank_id"
    if bank_file.exists():
        val = bank_file.read_text(encoding="utf-8").strip()
        if val:
            return val

    return env_bank or "brewline-demo-2"


BANK_ID = get_bank_id()


def is_mock() -> bool:
    return os.getenv("DEMO_MOCK") == "1"


BANK_MISSION = (
    "I am the memory of Priya Nair, shift manager at Brewline Cafe. I keep track of shift-swap "
    "agreements, who covered whose shift, disputes between employees, Priya's rulings, and standing "
    "policy exceptions, so future disputes can be settled from the written record and consistently."
)

import threading

_local = threading.local()
_mock_store: list[dict] = []


def _get_client():
    if not hasattr(_local, "client") or _local.client is None:
        from hindsight_client import Hindsight

        kwargs = {"base_url": os.environ["HINDSIGHT_BASE_URL"], "timeout": 60.0}
        if os.getenv("HINDSIGHT_API_KEY"):
            kwargs["api_key"] = os.environ["HINDSIGHT_API_KEY"]
        _local.client = Hindsight(**kwargs)
    return _local.client


def ensure_bank(bank_id: str | None = None) -> None:
    """Create the memory bank with its mission (harmless if it already exists)."""
    if is_mock():
        return
    target_bank = bank_id or get_bank_id()
    try:
        _get_client().create_bank(
            bank_id=target_bank,
            name="Brewline Swap Mediator",
            mission=BANK_MISSION,
            disposition={"skepticism": 4, "literalism": 4, "empathy": 3},
        )
    except Exception as e:  # bank probably exists; real auth errors will surface on retain
        print(f"[memory] create_bank skipped: {e}")


def retain(content: str, context: str | None = None, when: datetime | None = None, bank_id: str | None = None) -> None:
    if is_mock():
        _mock_store.append({"text": content, "type": "world"})
        return
    kwargs = {"bank_id": bank_id or get_bank_id(), "content": content, "retain_async": False}
    if context:
        kwargs["context"] = context
    if when:
        kwargs["timestamp"] = when
    _get_client().retain(**kwargs)


def recall(query: str, max_tokens: int = 1024, bank_id: str | None = None) -> list[dict]:
    """Return [{'text': ..., 'type': ...}] for the most relevant memories."""
    if is_mock():
        return _mock_recall(query)
    target_bank = bank_id or get_bank_id()
    res = _get_client().recall(bank_id=target_bank, query=query, max_tokens=max_tokens, budget="mid")
    return [{"text": r.text, "type": getattr(r, "type", None) or "memory"} for r in res.results]


# ---- offline mock -------------------------------------------------------------------------
_STOP = {"the", "and", "that", "with", "for", "his", "her", "she", "has", "was", "are", "who", "what",
         "says", "said", "this", "they", "not", "but", "you", "about", "there", "from", "have"}


def _tokens(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", s.lower()) if len(w) > 2 and w not in _STOP}


def _mock_recall(query: str) -> list[dict]:
    q = _tokens(query)
    scored = sorted(((len(q & _tokens(m["text"])), m) for m in _mock_store), key=lambda x: -x[0])
    return [m for score, m in scored[:6] if score > 0]
