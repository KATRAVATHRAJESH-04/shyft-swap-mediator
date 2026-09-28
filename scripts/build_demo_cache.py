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


BEAT_4_PROMPTS = {
    "Beat 4A: half-shift dispute": (
        "Sana covered 4 hours of Rohan's 8-hour shift yesterday. Sana says Rohan owes her a full shift back "
        "because she gave up her evening; Rohan says he only owes 4 hours or half a shift. What's the policy?"
    ),
    "Beat 4B: half-shift precedent": (
        "Aisha covered 4 hours of Tariq's shift on Thursday. Aisha says Tariq owes her a full shift back, "
        "but Tariq says he only owes half a shift. What's the ruling?"
    ),
}

BEAT_4_RULING = (
    "Priya ruled that half-shift covers count as half a shift (pro-rated repayment of 4 hours), "
    "establishing this as a standing policy for all staff."
)


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

    all_prompts = dict(DEMO_PROMPTS)

    for beat_name, prompt in all_prompts.items():
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

        norm_beat = normalize_query(beat_name)
        if norm_beat not in cache:
            cache[norm_beat] = cache[norm_key]

        print(f"  [OK] OFF words: {len(res_off['answer'].split())} | ON words: {len(res_on['answer'].split())}")
        time.sleep(2)

    # --- Beat 4: Learning Live (Dispute A -> Confirm Ruling -> Dispute B) ---
    print("\n>>> Running Beat 4: Learning live (isolated test bank) ...")
    
    # Beat 4A: Half-shift dispute (clean bank, no precedent)
    p4a = BEAT_4_PROMPTS["Beat 4A: half-shift dispute"]
    norm_4a = normalize_query(p4a)
    if norm_4a not in cache or "off" not in cache[norm_4a] or "on" not in cache[norm_4a]:
        print("  Processing Beat 4A (initial half-shift inquiry)...")
        off_4a, on_4a = safe_respond_compare(p4a)
        cache[norm_4a] = {
            "beat": "Beat 4A: half-shift dispute",
            "query": p4a,
            "off": {
                "answer": off_4a["answer"],
                "memories": off_4a.get("memories", []),
                "model": off_4a.get("model", os.getenv("FORCE_MODEL")),
            },
            "on": {
                "answer": on_4a["answer"],
                "memories": on_4a.get("memories", []),
                "model": on_4a.get("model", os.getenv("FORCE_MODEL")),
            },
        }
        cache[normalize_query("Beat 4A: half-shift dispute")] = cache[norm_4a]
        print(f"  [OK] Beat 4A OFF: {len(off_4a['answer'].split())}w | ON: {len(on_4a['answer'].split())}w")
        time.sleep(2)
    else:
        print("  [cached] Beat 4A already built.")

    # Beat 4B: Half-shift precedent (uses isolated bank 'learning-test' with confirmed ruling)
    p4b = BEAT_4_PROMPTS["Beat 4B: half-shift precedent"]
    norm_4b = normalize_query(p4b)
    if norm_4b not in cache or "off" not in cache[norm_4b] or "on" not in cache[norm_4b]:
        print("  Processing Beat 4B (applying learned precedent in isolated bank)...")
        orig_bank = os.environ.get("HINDSIGHT_BANK_ID", "brewline-demo-2")
        os.environ["HINDSIGHT_BANK_ID"] = "brewline-live-demo"
        try:
            memory.ensure_bank(bank_id="brewline-live-demo")
            # Retain Priya's confirmed ruling into isolated test bank
            memory.retain(
                f"Dispute on 2026-09-28: {p4a} Priya's ruling: {BEAT_4_RULING}",
                context="dispute ruling",
                when="2026-09-28",
                bank_id="brewline-live-demo",
            )
            time.sleep(1)
            off_4b, on_4b = safe_respond_compare(p4b)
            cache[norm_4b] = {
                "beat": "Beat 4B: half-shift precedent",
                "query": p4b,
                "off": {
                    "answer": off_4b["answer"],
                    "memories": off_4b.get("memories", []),
                    "model": off_4b.get("model", os.getenv("FORCE_MODEL")),
                },
                "on": {
                    "answer": on_4b["answer"],
                    "memories": on_4b.get("memories", []),
                    "model": on_4b.get("model", os.getenv("FORCE_MODEL")),
                },
            }
            cache[normalize_query("Beat 4B: half-shift precedent")] = cache[norm_4b]
            print(f"  [OK] Beat 4B OFF: {len(off_4b['answer'].split())}w | ON: {len(on_4b['answer'].split())}w")
        finally:
            os.environ["HINDSIGHT_BANK_ID"] = orig_bank
    else:
        print("  [cached] Beat 4B already built.")

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)

    print(f"\n[DONE] Successfully saved demo cache to: {CACHE_FILE}")


if __name__ == "__main__":
    build_cache()
