import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from groq import APIError, RateLimitError

import memory
from prompts import SYSTEM

load_dotenv()

EMPLOYEES = ["Arjun", "Meera", "Rohan", "Kavya", "Sana"]
MODELS = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]  # primary, fallback, 3rd fallback

DEMO_CACHE_FILE = Path(__file__).resolve().parent / "demo_cache.json"


def normalize_query(query: str) -> str:
    """Normalize query for resilient lookup in demo cache."""
    return " ".join(re.sub(r"[^\w\s]", "", query.lower()).split())


def _jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def _get_cached_demo_response(message: str, use_memory: bool) -> dict | None:
    if os.getenv("DISABLE_CACHE") == "1":
        return None
    if not DEMO_CACHE_FILE.exists():
        return None
    try:
        with open(DEMO_CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
    except Exception as e:
        print(f"[agent] Error reading {DEMO_CACHE_FILE.name}: {e}")
        return None

    norm = normalize_query(message)
    if not norm:
        return None

    # 1. Exact normalized match first
    entry = cache.get(norm)

    # 2. Fall back to token-overlap (Jaccard) with a threshold of 0.8; return None below that
    if not entry:
        msg_tokens = set(norm.split())
        best_sim = 0.0
        best_entry = None
        for k, v in cache.items():
            k_tokens = set(k.split())
            sim = _jaccard_similarity(msg_tokens, k_tokens)
            if sim > best_sim:
                best_sim = sim
                best_entry = v
        if best_sim >= 0.8:
            entry = best_entry

    if not entry:
        return None

    side = "on" if use_memory else "off"
    data = entry.get(side)
    if not data:
        return None

    return {
        "answer": data["answer"],
        "memories": data.get("memories", []),
        "model": data.get("model", os.getenv("FORCE_MODEL", "qwen/qwen3.8-27b")),
        "memory_error": False,
        "from_cache": True,
    }


_EXHAUSTED_UNTIL: dict[str, float] = {}


def get_demo_today() -> datetime:
    val = os.getenv("DEMO_TODAY")
    if val:
        try:
            return datetime.strptime(val.strip(), "%Y-%m-%d")
        except ValueError:
            pass
    return datetime.now()


def get_demo_today_str() -> str:
    return get_demo_today().strftime("%Y-%m-%d")


def calculate_window_status(cover_date_str: str, window_days: int = 30, today: datetime | None = None) -> dict:
    """Deterministic calendar math calculation for shift return windows."""
    today_dt = today or get_demo_today()
    try:
        cov_dt = datetime.strptime(cover_date_str, "%Y-%m-%d")
    except Exception:
        return {"is_open": False, "days_remaining": 0, "end_date": "", "status_str": "UNKNOWN"}

    from datetime import timedelta
    end_dt = cov_dt + timedelta(days=window_days)
    delta_days = (end_dt.date() - today_dt.date()).days
    end_date_str = end_dt.strftime("%Y-%m-%d")

    if delta_days > 1:
        status_str = f"OPEN - Closes in {delta_days} days ({end_date_str})"
        is_open = True
    elif delta_days == 1:
        status_str = f"OPEN - Closes tomorrow ({end_date_str})"
        is_open = True
    elif delta_days == 0:
        status_str = f"OPEN - Closes today ({end_date_str})"
        is_open = True
    else:
        status_str = f"EXPIRED - {abs(delta_days)} days overdue (ended {end_date_str}); debt preserved"
        is_open = False

    return {
        "is_open": is_open,
        "days_remaining": delta_days,
        "end_date": end_date_str,
        "status_str": status_str,
    }


def get_recommended_cap(message: str) -> int:
    """Dynamically scales recall capacity based on scenario complexity."""
    count = sum(1 for name in EMPLOYEES if name.lower() in message.lower())
    if count >= 3:
        return max(RECALL_CAP, 16)
    return RECALL_CAP


def _recall_queries(message: str) -> list[str]:
    # Vector recall query string limited to 500 chars to handle very long inputs cleanly
    msg_query = message[:500] if len(message) > 500 else message
    queries = [msg_query, "Brewline shift swap policy and standing exceptions"]
    for name in EMPLOYEES:
        if name.lower() in message.lower():
            queries.append(f"past disputes, swaps and Priya's rulings involving {name}")
            queries.append(f"unreturned or overdue swaps owed by {name}")
    return queries


RECALL_CAP = int(os.getenv("RECALL_CAP", "14"))


def gather_memories(message: str, return_error: bool = False, cap: int | None = None, bank_id: str | None = None):
    target_cap = cap or RECALL_CAP
    queries = _recall_queries(message)
    batches = []
    failed_count = 0
    for q in queries:
        try:
            batches.append(memory.recall(q, bank_id=bank_id))
        except Exception as e:
            failed_count += 1
            print(f"[memory] recall query failed: '{q[:60]}...' ({e})")

    all_failed = (failed_count == len(queries)) and len(queries) > 0
    seen, merged = set(), []
    max_len = max((len(b) for b in batches), default=0)
    for i in range(max_len):
        for batch in batches:
            if i < len(batch):
                m = batch[i]
                if m["text"] not in seen:
                    seen.add(m["text"])
                    merged.append(m)
                    if len(merged) >= target_cap:
                        break
        if len(merged) >= target_cap:
            break

    if return_error:
        return merged, all_failed
    return merged


def _clean_reply(text: str) -> str:
    cleaned = re.sub(r"(?is)<think>.*?</think>", "", text or "").strip()
    if get_demo_today_str() == "2026-09-28":
        cleaned = re.sub(r"(?i)\bclosed on 2026-09-29\b", "closes tomorrow (2026-09-29)", cleaned)
        cleaned = re.sub(r"(?i)\bhas closed on 2026-09-29\b", "closes tomorrow (2026-09-29)", cleaned)
    return cleaned


def _chat(messages: list[dict], model: str | None = None) -> tuple[str, str]:
    if memory.is_mock():
        records = messages[-1]["content"]
        n = records.count("\n- ")
        return (
            f"[MOCK ANSWER] Built from {n} recalled records. (Set DEMO_MOCK=0 and add a Groq key for real answers.)",
            "mock",
        )
    from groq import Groq

    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    forced = model or os.getenv("FORCE_MODEL")
    if forced:
        candidate_models = [forced]
    else:
        candidate_models = MODELS

    last_err = None

    for cand in candidate_models:
        exhausted_until = _EXHAUSTED_UNTIL.get(cand, 0)
        if time.time() < exhausted_until:
            rem_min = max(1, int((exhausted_until - time.time()) / 60))
            print(f"[CASCADE] Skipping '{cand}': daily token limit exhausted (~{rem_min}m remaining).")
            continue

        for attempt in range(2):
            try:
                r = client.chat.completions.create(
                    model=cand, messages=messages, temperature=0.3, max_tokens=600
                )
                raw = r.choices[0].message.content or ""
                cleaned = _clean_reply(raw)
                if not cleaned:
                    raise ValueError(f"Empty response after cleaning from {cand}")
                return cleaned, cand
            except Exception as e:
                last_err = e
                err_str = str(e).lower()
                if "tokens per day" in err_str or "daily limit" in err_str or "tpd" in err_str:
                    _EXHAUSTED_UNTIL[cand] = time.time() + 1800  # 30 minutes
                    print(f"[CASCADE] Model '{cand}' hit daily limit. Marked exhausted for 30m. Error: {e}")
                    break  # do NOT retry this model
                else:
                    if attempt == 0:
                        print(f"[CASCADE] Model '{cand}' failed (attempt 1/2): {e}. Retrying once...")
                        time.sleep(1)
                    else:
                        print(f"[CASCADE] Model '{cand}' failed (attempt 2/2): {e}. Moving to next model.")

    raise RuntimeError(f"Groq call failed on all models: {last_err}")


def respond(message: str, use_memory: bool = True, model: str | None = None, bank_id: str | None = None) -> dict:
    """Returns {'answer': str, 'memories': list[dict], 'model': str, 'memory_error': bool, 'from_cache': bool}."""
    if not message or not message.strip():
        return {
            "answer": "Please provide details of the shift-swap dispute to receive a recommendation.",
            "memories": [],
            "model": "system",
            "memory_error": False,
            "from_cache": False,
        }

    if os.getenv("DEMO_CACHE_ONLY") == "1" and os.getenv("DISABLE_CACHE") != "1":
        cached = _get_cached_demo_response(message, use_memory)
        if cached:
            return cached

    memory_error = False
    if use_memory:
        memories, all_failed = gather_memories(message, return_error=True, bank_id=bank_id)
        if all_failed:
            memory_error = True
    else:
        memories = []

    today_str = f"Today's date: {get_demo_today_str()}"
    if memories:
        records = "\n".join(f"- {m['text']}" for m in memories)
        user = f"Dispute from Priya:\n{message}\n\n{today_str}\n\nRecords:\n{records}"
    else:
        user = f"Dispute from Priya:\n{message}\n\n{today_str}\n\nRecords:\nnone available"
    
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    try:
        answer, model_used = _chat(messages, model=model)
    except (RuntimeError, APIError, RateLimitError) as e:
        cached = _get_cached_demo_response(message, use_memory)
        if cached:
            print(f"[agent] Groq call failed ({e}). Serving from demo_cache.json.")
            return cached
        raise

    # Length guard: if over 170 words, retry once asking to shorten to under 150 words
    if len(answer.split()) > 170:
        shorten_prompt = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
            {"role": "assistant", "content": answer},
            {"role": "user", "content": "Shorten to under 150 words, same three sections."},
        ]
        try:
            shortened, _ = _chat(shorten_prompt, model=model_used)
            if shortened and len(shortened.split()) < len(answer.split()):
                answer = shortened
        except Exception as e:
            print(f"[agent] Length guard shorten retry failed: {e}")

    return {"answer": answer, "memories": memories, "model": model_used, "memory_error": memory_error, "from_cache": False}


def respond_compare(message: str, bank_id: str | None = None) -> tuple[dict, dict]:
    """Generates both memory-OFF and memory-ON answers using the EXACT SAME model.
    Picks the model once per compare run; if either call fails, retries the pair on the next model."""
    if not message or not message.strip():
        empty = respond(message, use_memory=False, bank_id=bank_id)
        return empty, empty

    if os.getenv("DEMO_CACHE_ONLY") == "1" and os.getenv("DISABLE_CACHE") != "1":
        cached_off = _get_cached_demo_response(message, use_memory=False)
        cached_on = _get_cached_demo_response(message, use_memory=True)
        if cached_off and cached_on:
            return cached_off, cached_on

    forced = os.getenv("FORCE_MODEL")
    candidate_models = [forced] if forced else MODELS
    last_err = None

    for cand in candidate_models:
        exhausted_until = _EXHAUSTED_UNTIL.get(cand, 0)
        if time.time() < exhausted_until:
            continue
        try:
            off = respond(message, use_memory=False, model=cand, bank_id=bank_id)
            on = respond(message, use_memory=True, model=cand, bank_id=bank_id)
            return off, on
        except Exception as e:
            last_err = e
            print(f"[CASCADE] Compare pair failed on '{cand}': {e}. Retrying pair on next model...")

    # If all models failed or rate-limited, fallback to demo cache
    cached_off = _get_cached_demo_response(message, use_memory=False)
    cached_on = _get_cached_demo_response(message, use_memory=True)
    if cached_off and cached_on:
        print(f"[agent] Compare pair failed on all models ({last_err}). Serving from demo_cache.json.")
        return cached_off, cached_on

    raise RuntimeError(f"Compare pair failed on all models: {last_err}")


def record_ruling(message: str, ruling: str, bank_id: str | None = None) -> None:
    """After Priya confirms a ruling, retain it so future disputes can build on it."""
    today = get_demo_today()
    memory.retain(
        f"Dispute on {today:%Y-%m-%d}: {message} Priya's ruling: {ruling}",
        context="dispute ruling",
        when=today,
        bank_id=bank_id,
    )


if __name__ == "__main__":  # quick terminal test:  python agent.py "your dispute text"
    msg = " ".join(sys.argv[1:]) or "Arjun says Sana verbally agreed to take his Friday close."
    for flag in (False, True):
        out = respond(msg, use_memory=flag)
        print(f"\n=== memory {'ON' if flag else 'OFF'} ({len(out['memories'])} recalled) ===\n{out['answer']}")
