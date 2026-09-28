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
os.environ["FORCE_MODEL"] = "qwen/qwen3.8-27b"

import agent
import memory
from prompts import DEMO_PROMPTS


def split_sentences(text: str) -> list[str]:
    # Split text into lines, bullets, and sentences
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    sentences = []
    for line in lines:
        parts = re.split(r"(?<=[.!?])\s+", line)
        for p in parts:
            if p.strip():
                sentences.append(p.strip())
    return sentences


def grade_answer(answer: str, label: str = "") -> dict:
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
            # Exemption: starts with "you note" / "you say" or quotes policy
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

    return {
        "words": words,
        "word_pass": word_pass,
        "attr_pass": attr_pass,
        "violations": attribution_violations,
    }


def main():
    print("================================================================================")
    print("FINAL TUNING VERIFICATION & GRADER REPORT")
    print(f"Bank: {memory.get_bank_id()} | FORCE_MODEL: {os.getenv('FORCE_MODEL')}")
    print("================================================================================\n")

    # 1. Beat 2 ON
    print(">>> [TEST 1] Beat 2 ON: Expired Swap Window <<<")
    b2_prompt = DEMO_PROMPTS["Beat 2: expired swap window"]
    res_b2 = agent.respond(b2_prompt, use_memory=True)
    g_b2 = grade_answer(res_b2["answer"], "Beat 2 ON")
    print(f"Model: {res_b2.get('model')} | Words: {g_b2['words']} ({'PASS' if g_b2['word_pass'] else 'FAIL'}) | Attribution: {'PASS' if g_b2['attr_pass'] else 'FAIL'}")
    if g_b2["violations"]:
        print(f"  Violations: {g_b2['violations']}")
    print("\nAnswer:")
    print(res_b2["answer"])
    print("\n" + "-" * 70 + "\n")

    # 2. Beat 3 ON (3 times)
    b3_prompt = DEMO_PROMPTS["Beat 3: spot the pattern"]
    for i in range(1, 4):
        print(f">>> [TEST {1+i}] Beat 3 ON (Run {i}/3): Spot the Pattern <<<")
        res_b3 = agent.respond(b3_prompt, use_memory=True)
        g_b3 = grade_answer(res_b3["answer"], f"Beat 3 ON Run {i}")
        print(f"Model: {res_b3.get('model')} | Words: {g_b3['words']} ({'PASS' if g_b3['word_pass'] else 'FAIL'}) | Attribution: {'PASS' if g_b3['attr_pass'] else 'FAIL'}")
        if g_b3["violations"]:
            print(f"  Violations: {g_b3['violations']}")
        print("\nAnswer:")
        print(res_b3["answer"])
        print("\n" + "-" * 70 + "\n")

    # 3. Cold-Start case
    print(">>> [TEST 5] Cold-Start Case: Unknown Staff (Aisha & Tariq) <<<")
    cold_prompt = "Aisha covered Tariq's shift 45 days ago and Tariq refuses to return it."
    res_cold = agent.respond(cold_prompt, use_memory=True)
    g_cold = grade_answer(res_cold["answer"], "Cold-Start")
    print(f"Model: {res_cold.get('model')} | Words: {g_cold['words']} ({'PASS' if g_cold['word_pass'] else 'FAIL'}) | Attribution: {'PASS' if g_cold['attr_pass'] else 'FAIL'}")
    if g_cold["violations"]:
        print(f"  Violations: {g_cold['violations']}")
    print("\nAnswer:")
    print(res_cold["answer"])
    print("\n" + "-" * 70 + "\n")

    # 4. Beat 1 Full Compare Run
    print(">>> [TEST 6] Beat 1 Compare Run (Both Columns with respond_compare) <<<")
    b1_prompt = DEMO_PROMPTS["Beat 1: festival shift math"]
    res_off, res_on = agent.respond_compare(b1_prompt)
    g_off = grade_answer(res_off["answer"], "Beat 1 OFF")
    g_on = grade_answer(res_on["answer"], "Beat 1 ON")
    models_match = (res_off.get("model") == res_on.get("model"))

    print(f"Model OFF: {res_off.get('model')} | Model ON: {res_on.get('model')} | Models Match: {'PASS' if models_match else 'FAIL'}")
    print(f"OFF Words: {g_off['words']} ({'PASS' if g_off['word_pass'] else 'FAIL'}) | OFF Attribution: {'PASS' if g_off['attr_pass'] else 'FAIL'}")
    print(f"ON Words:  {g_on['words']} ({'PASS' if g_on['word_pass'] else 'FAIL'}) | ON Attribution:  {'PASS' if g_on['attr_pass'] else 'FAIL'}")
    
    print("\n--- Memory OFF Column ---")
    print(res_off["answer"])
    print("\n--- Memory ON Column ---")
    print(res_on["answer"])
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
