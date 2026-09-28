import os
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

import agent
import memory
from prompts import DEMO_PROMPTS


def main():
    print("================================================================================")
    print("STAGE 3 LAST-PASS EVALUATION & STAGE 4 COMPARE-MODE TIMING REPORT")
    print(f"Bank: {memory.get_bank_id()}")
    print("================================================================================\n")

    beats = [
        ("Beat 1", "Beat 1: festival shift math", DEMO_PROMPTS["Beat 1: festival shift math"]),
        ("Beat 2", "Beat 2: expired swap window", DEMO_PROMPTS["Beat 2: expired swap window"]),
        ("Beat 3", "Beat 3: spot the pattern", DEMO_PROMPTS["Beat 3: spot the pattern"]),
    ]

    timings = []
    answers_log = []

    # 1. Beats 1-3: memory-OFF and memory-ON
    for beat_num, label, prompt in beats:
        print(f"\n{'='*70}\n>>> {label.upper()} <<<\n{'='*70}")
        print(f"Dispute: \"{prompt}\"\n")

        # Memory OFF
        t0 = time.perf_counter()
        res_off = agent.respond(prompt, use_memory=False)
        t_off = time.perf_counter() - t0

        print(f"--- [MEMORY OFF] (Model: {res_off.get('model')}, Words: {len(res_off['answer'].split())}, Time: {t_off:.2f}s) ---")
        print(res_off["answer"])
        print()

        # Memory ON
        t0 = time.perf_counter()
        res_on = agent.respond(prompt, use_memory=True)
        t_on = time.perf_counter() - t0

        print(f"--- [MEMORY ON] (Model: {res_on.get('model')}, Words: {len(res_on['answer'].split())}, Memories: {len(res_on['memories'])}, Time: {t_on:.2f}s) ---")
        print(res_on["answer"])
        print()

        t_compare = t_off + t_on
        timings.append({
            "beat": beat_num,
            "label": label,
            "t_off": t_off,
            "t_on": t_on,
            "t_compare": t_compare,
            "model_off": res_off.get("model"),
            "model_on": res_on.get("model"),
        })
        answers_log.append((f"{beat_num} OFF", res_off))
        answers_log.append((f"{beat_num} ON (run 1)", res_on))

    # 2. Beat 3: memory-ON 3 more times to verify consistency
    beat3_prompt = DEMO_PROMPTS["Beat 3: spot the pattern"]
    print(f"\n{'='*70}\n>>> BEAT 3 MEMORY-ON CONSISTENCY CHECKS (RUNS 2, 3, 4) <<<\n{'='*70}")
    for run_idx in (2, 3, 4):
        t0 = time.perf_counter()
        res_on = agent.respond(beat3_prompt, use_memory=True)
        t_on = time.perf_counter() - t0
        print(f"--- [BEAT 3 MEMORY ON - RUN {run_idx}] (Model: {res_on.get('model')}, Words: {len(res_on['answer'].split())}, Memories: {len(res_on['memories'])}, Time: {t_on:.2f}s) ---")
        print(res_on["answer"])
        print()
        answers_log.append((f"Beat 3 ON (run {run_idx})", res_on))

    # 3. Print Stage 4 Timing Report
    print("\n================================================================================")
    print("STAGE 4 COMPARE-MODE TIMING REPORT")
    print("================================================================================")
    print(f"{'Beat':<10} | {'Memory OFF':<12} | {'Memory ON':<12} | {'Compare Mode Total':<18} | {'Model ON'}")
    print("-" * 75)
    for row in timings:
        print(f"{row['beat']:<10} | {row['t_off']:>10.2f}s | {row['t_on']:>10.2f}s | {row['t_compare']:>16.2f}s | {row['model_on']}")
    avg_off = sum(r['t_off'] for r in timings) / len(timings)
    avg_on = sum(r['t_on'] for r in timings) / len(timings)
    avg_comp = sum(r['t_compare'] for r in timings) / len(timings)
    print("-" * 75)
    print(f"{'AVERAGE':<10} | {avg_off:>10.2f}s | {avg_on:>10.2f}s | {avg_comp:>16.2f}s |")
    print("================================================================================\n")


if __name__ == "__main__":
    main()
