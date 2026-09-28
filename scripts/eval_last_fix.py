import os
import re
import sys
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
os.environ["FORCE_MODEL"] = "qwen/qwen3.8-27b"
os.environ["DEMO_TODAY"] = "2026-09-28"

import agent
import memory
from prompts import DEMO_PROMPTS


def split_sentences(text: str) -> list[str]:
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    sentences = []
    for line in lines:
        parts = re.split(r"(?<=[.!?])\s+", line)
        for p in parts:
            if p.strip():
                sentences.append(p.strip())
    return sentences


def grade_answer(answer: str, is_memory_off: bool = False, demo_today: str = "2026-09-28", memories: list[dict] = None) -> dict:
    words = len(answer.split())
    word_pass = words <= 170

    sentences = split_sentences(answer)
    attribution_violations = []

    for s in sentences:
        s_lower = s.lower().lstrip("-* \t")
        has_app = ("app" in s_lower or "shyft" in s_lower)
        has_neg = any(w in s_lower for w in ["no ", "no-", "nothing", "not ", "n't", "none "])
        has_rec = any(w in s_lower for w in ["logged", "recorded", "entry", "record", "exists", "exist"])

        if has_app and has_neg and has_rec:
            if (
                s_lower.startswith("you note")
                or s_lower.startswith("you say")
                or "policy" in s_lower
                or "precedent" in s_lower
                or "ruled" in s_lower
            ):
                continue
            attribution_violations.append(s)

    attr_pass = len(attribution_violations) == 0

    # Window wording check
    ans_lower = answer.lower()
    window_pass = True
    window_reason = "OK"

    # Check for both 'closed' and 'closes' about the same window
    if "closed" in ans_lower and "closes" in ans_lower:
        window_pass = False
        window_reason = "Answer uses both 'closed' and 'closes' about window"

    # If demo_today is 2026-09-28, a window ending 2026-09-29 is on or after demo_today (still open)
    # Check if answer claims 2026-09-29 is closed or expired
    if demo_today == "2026-09-28":
        if "2026-09-29" in answer:
            # Check lines/sentences mentioning 2026-09-29
            for s in sentences:
                if "2026-09-29" in s:
                    s_low = s.lower()
                    if "closed" in s_low or "expired" in s_low or "has expired" in s_low or "was expired" in s_low:
                        window_pass = False
                        window_reason = f"Window ending 2026-09-29 reported closed/expired when demo_today is {demo_today}"

    # If demo_today is 2026-10-02, the window 2026-09-29 is BEFORE demo_today -> must say expired and debt stands per 2026-07-26
    if demo_today == "2026-10-02":
        if "expired" not in ans_lower:
            window_pass = False
            window_reason = "Expected window to be reported expired for demo_today=2026-10-02"
        if "2026-07-26" not in answer:
            window_pass = False
            window_reason = "Expected citation of 2026-07-26 ruling for expired window"

    # Pattern bullet check
    pattern_pass = True
    pattern_reason = "OK"
    pattern_lines = [line for line in answer.split("\n") if "pattern:" in line.lower()]

    if pattern_lines:
        pat_text = pattern_lines[0]
        # Banned: 'on time' unless record says so
        if "on time" in pat_text.lower():
            pattern_pass = False
            pattern_reason = "Pattern bullet describes return as 'on time'"

        # Event count: separated by ';'
        events = [e.strip() for e in pat_text.split(";") if e.strip()]
        if len(events) < 2:
            pattern_pass = False
            pattern_reason = f"Pattern bullet has fewer than 2 events ({len(events)} found)"

        # If memories provided, check if August covers appear in recalled memories
        if memories:
            recalled_august = any(
                ("08-08" in m["text"] or "08-22" in m["text"] or "august 8" in m["text"].lower() or "no return" in m["text"].lower())
                for m in memories
            )
            if recalled_august:
                pat_lower = pat_text.lower()
                has_aug_mention = any(k in pat_lower for k in ["august", "09-07", "09-21", "covers overdue", "overdue since"])
                if not has_aug_mention:
                    pattern_pass = False
                    pattern_reason = "Pattern omits August covers when they are in recalled list"

    # Memory OFF evidence bullets check (at most 2 bullets)
    off_evidence_pass = True
    if is_memory_off:
        evidence_lines = []
        in_ev = False
        for line in answer.split("\n"):
            if "2. evidence" in line.lower() or "**evidence**" in line.lower() or "evidence" == line.strip().lower():
                in_ev = True
                continue
            if in_ev:
                if "3. what" in line.lower() or "**what" in line.lower() or line.startswith("3."):
                    break
                if line.strip().startswith("-") or line.strip().startswith("*"):
                    evidence_lines.append(line.strip())
        if len(evidence_lines) > 2:
            off_evidence_pass = False

    return {
        "words": words,
        "word_pass": word_pass,
        "attr_pass": attr_pass,
        "violations": attribution_violations,
        "window_pass": window_pass,
        "window_reason": window_reason,
        "pattern_pass": pattern_pass,
        "pattern_reason": pattern_reason,
        "off_evidence_pass": off_evidence_pass,
    }


import json
import time

CACHE_FILE = ROOT / "scripts" / "eval_last_fix_cache.json"


def load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_cache(cache: dict) -> None:
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(f"[cache error] {e}")


def parse_groq_wait(err_msg: str) -> float:
    m = re.search(r"try again in (?:(\d+)m)?([\d\.]+)s", err_msg)
    if m:
        mins = int(m.group(1)) if m.group(1) else 0
        secs = float(m.group(2))
        return mins * 60 + secs
    return 60.0


def safe_respond(prompt: str, use_memory: bool = True, demo_today: str = "2026-09-28") -> dict:
    os.environ["DEMO_TODAY"] = demo_today
    while True:
        try:
            return agent.respond(prompt, use_memory=use_memory)
        except Exception as e:
            err_str = str(e)
            if "tokens per day" in err_str.lower() or "rate_limit_exceeded" in err_str.lower() or "daily limit" in err_str.lower():
                wait_sec = parse_groq_wait(err_str) + 5
                print(f"[eval] Rate limit reached. Waiting {wait_sec:.1f}s until reset...")
                time.sleep(wait_sec)
                agent._EXHAUSTED_UNTIL.clear()
            else:
                raise


def safe_respond_compare(prompt: str, demo_today: str = "2026-09-28") -> tuple[dict, dict]:
    os.environ["DEMO_TODAY"] = demo_today
    while True:
        try:
            return agent.respond_compare(prompt)
        except Exception as e:
            err_str = str(e)
            if "tokens per day" in err_str.lower() or "rate_limit_exceeded" in err_str.lower() or "daily limit" in err_str.lower():
                wait_sec = parse_groq_wait(err_str) + 5
                print(f"[eval] Rate limit reached. Waiting {wait_sec:.1f}s until reset...")
                time.sleep(wait_sec)
                agent._EXHAUSTED_UNTIL.clear()
            else:
                raise


def main():
    print("================================================================================")
    print("LAST FIX EVALUATION & GRADER REPORT")
    print(f"Bank: {memory.get_bank_id()} | FORCE_MODEL: {os.getenv('FORCE_MODEL')}")
    print("================================================================================\n")

    cache = load_cache()

    # 1. Beat 1 Compare Run (demo_today = 2026-09-28)
    print(">>> [TEST 1] Beat 1 Compare Run (DEMO_TODAY=2026-09-28) <<<")
    os.environ["DEMO_TODAY"] = "2026-09-28"
    b1_prompt = DEMO_PROMPTS["Beat 1: festival shift math"]

    if "test_1" in cache:
        res_off = cache["test_1"]["off"]
        res_on = cache["test_1"]["on"]
        # re-attach memories for grading
        res_on["memories"] = agent.gather_memories(b1_prompt)
    else:
        res_off, res_on = safe_respond_compare(b1_prompt, demo_today="2026-09-28")
        cache["test_1"] = {
            "off": {"model": res_off.get("model"), "answer": res_off["answer"]},
            "on": {"model": res_on.get("model"), "answer": res_on["answer"]},
        }
        save_cache(cache)
    
    g_off = grade_answer(res_off["answer"], is_memory_off=True, demo_today="2026-09-28")
    g_on = grade_answer(res_on["answer"], is_memory_off=False, demo_today="2026-09-28", memories=res_on.get("memories"))
    models_match = (res_off.get("model") == res_on.get("model"))

    print(f"Models Match: {'PASS' if models_match else 'FAIL'} (OFF: {res_off.get('model')}, ON: {res_on.get('model')})")
    print(f"OFF: Words={g_off['words']} ({'PASS' if g_off['word_pass'] else 'FAIL'}), Attribution={'PASS' if g_off['attr_pass'] else 'FAIL'}, Evidence Bullets <= 2: {'PASS' if g_off['off_evidence_pass'] else 'FAIL'}")
    print(f"ON:  Words={g_on['words']} ({'PASS' if g_on['word_pass'] else 'FAIL'}), Attribution={'PASS' if g_on['attr_pass'] else 'FAIL'}, Window Wording={'PASS' if g_on['window_pass'] else 'FAIL'} ({g_on['window_reason']})")

    print("\n--- Memory OFF Column ---")
    print(res_off["answer"])
    print("\n--- Memory ON Column ---")
    print(res_on["answer"])
    print("\n" + "-" * 70 + "\n")

    # 2. Beat 3 Memory ON (3 runs, demo_today = 2026-09-28)
    b3_prompt = DEMO_PROMPTS["Beat 3: spot the pattern"]
    for i in range(1, 4):
        test_key = f"test_{1+i}"
        print(f">>> [TEST {1+i}] Beat 3 Memory ON (Run {i}/3) (DEMO_TODAY=2026-09-28) <<<")
        if test_key in cache:
            res_b3 = cache[test_key]
            res_b3["memories"] = agent.gather_memories(b3_prompt)
        else:
            time.sleep(2)
            res_b3 = safe_respond(b3_prompt, use_memory=True, demo_today="2026-09-28")
            cache[test_key] = {"model": res_b3.get("model"), "answer": res_b3["answer"]}
            save_cache(cache)

        g_b3 = grade_answer(res_b3["answer"], is_memory_off=False, demo_today="2026-09-28", memories=res_b3.get("memories"))
        print(f"Model: {res_b3.get('model')} | Words: {g_b3['words']} ({'PASS' if g_b3['word_pass'] else 'FAIL'}) | Attribution: {'PASS' if g_b3['attr_pass'] else 'FAIL'} | Pattern: {'PASS' if g_b3['pattern_pass'] else 'FAIL'} ({g_b3['pattern_reason']})")
        if g_b3["violations"]:
            print(f"  Attribution Violations: {g_b3['violations']}")
        print("\nAnswer:")
        print(res_b3["answer"])
        print("\n" + "-" * 70 + "\n")

    # 3. Beat 1 Memory ON with DEMO_TODAY = 2026-10-02 (Window expired check)
    print(">>> [TEST 5] Beat 1 Memory ON with DEMO_TODAY=2026-10-02 <<<")
    if "test_5" in cache:
        res_b1_future = cache["test_5"]
        res_b1_future["memories"] = agent.gather_memories(b1_prompt)
    else:
        time.sleep(2)
        res_b1_future = safe_respond(b1_prompt, use_memory=True, demo_today="2026-10-02")
        cache["test_5"] = {"model": res_b1_future.get("model"), "answer": res_b1_future["answer"]}
        save_cache(cache)

    g_b1_fut = grade_answer(res_b1_future["answer"], is_memory_off=False, demo_today="2026-10-02", memories=res_b1_future.get("memories"))
    print(f"Model: {res_b1_future.get('model')} | Words: {g_b1_fut['words']} ({'PASS' if g_b1_fut['word_pass'] else 'FAIL'}) | Attribution: {'PASS' if g_b1_fut['attr_pass'] else 'FAIL'} | Expired Window & Debt Ruling: {'PASS' if g_b1_fut['window_pass'] else 'FAIL'} ({g_b1_fut['window_reason']})")
    print("\nAnswer:")
    print(res_b1_future["answer"])
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()

