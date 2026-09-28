"""build_demo_cache.py - Precomputes and caches high-quality responses for the 3 demo beats.

Runs each demo beat with memory ON and OFF using the pinned model, and writes
demo_cache.json to serve as a demo-safe fallback if Groq rate-limits.
"""

import json
import os
import re
import sys
import time
from pathlib import Path

# Ensure UTF-8 output encoding on Windows console
if sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

os.environ["DEMO_MOCK"] = "0"
os.environ["FORCE_MODEL"] = os.getenv("FORCE_MODEL", "qwen/qwen3.8-27b")
os.environ["DEMO_TODAY"] = "2026-09-28"
os.environ["DEMO_CACHE_ONLY"] = "0"

import agent
import memory
from prompts import DEMO_PROMPTS

CACHE_FILE = ROOT / "demo_cache.json"


def normalize_query(query: str) -> str:
    """Lowercase and remove non-alphanumeric chars to create a robust lookup key."""
    return " ".join(re.sub(r"[^\w\s]", "", query.lower()).split())


def parse_groq_wait(err_msg: str) -> float:
    m = re.search(r"try again in (?:(\d+)m)?([\d\.]+)s", err_msg)
    if m:
        mins = int(m.group(1)) if m.group(1) else 0
        secs = float(m.group(2))
        return mins * 60 + secs
    return 60.0


def safe_respond_compare(prompt: str) -> tuple[dict, dict]:
    while True:
        try:
            return agent.respond_compare(prompt)
        except Exception as e:
            err_str = str(e)
            if any(k in err_str.lower() for k in ["tokens per day", "rate_limit_exceeded", "daily limit", "tpd"]):
                wait_sec = parse_groq_wait(err_str) + 5
                print(f"[build_cache] Rate limit reached. Waiting {wait_sec:.1f}s until reset...")
                time.sleep(wait_sec)
                agent._EXHAUSTED_UNTIL.clear()
            else:
                raise


def build_cache() -> None:
    print("================================================================================")
    print("BUILDING DEMO CACHE FOR GROQ RATE-LIMIT FALLBACK")
    print(f"Bank: {memory.get_bank_id()} | Model: {os.getenv('FORCE_MODEL')}")
    print("================================================================================\n")

    cache = {}
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            cache = {}

    for beat_name, prompt in DEMO_PROMPTS.items():
        norm_key = normalize_query(prompt)
        print(f">>> Running {beat_name} ...")
        
        # Check if already present and complete
        if norm_key in cache and "off" in cache[norm_key] and "on" in cache[norm_key]:
            print(f"  [cached] Already built in {CACHE_FILE.name}")
            continue

        res_off, res_on = safe_respond_compare(prompt)

        cache[norm_key] = {
            "beat": beat_name,
            "query": prompt,
            "off": {
                "answer": res_off["answer"],
                "memories": res_off.get("memories", []),
                "model": res_off.get("model", os.getenv("FORCE_MODEL")),
            },
            "on": {
                "answer": res_on["answer"],
                "memories": res_on.get("memories", []),
                "model": res_on.get("model", os.getenv("FORCE_MODEL")),
            },
        }

        # Also store under normalized beat name for convenience
        norm_beat = normalize_query(beat_name)
        if norm_beat not in cache:
            cache[norm_beat] = cache[norm_key]

        print(f"  [OK] OFF words: {len(res_off['answer'].split())} | ON words: {len(res_on['answer'].split())}")
        time.sleep(2)

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)

    print(f"\n[DONE] Successfully saved demo cache to: {CACHE_FILE}")


if __name__ == "__main__":
    build_cache()
