import os
import sys
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

os.environ["DEMO_MOCK"] = "0"
import agent
import memory
from prompts import DEMO_PROMPTS


def match_beat1(memories):
    checks = {
        "2026-07-20 festival exception (festival shift = 2 shifts)": None,
        "2026-08-30 Kavya covered Rohan record": None,
    }
    for idx, m in enumerate(memories, 1):
        t = m["text"].lower()
        if checks["2026-07-20 festival exception (festival shift = 2 shifts)"] is None:
            if ("festival" in t or "festive" in t) and ("two" in t or "2" in t) and ("shift" in t):
                checks["2026-07-20 festival exception (festival shift = 2 shifts)"] = idx
        if checks["2026-08-30 Kavya covered Rohan record"] is None:
            if "kavya" in t and "rohan" in t and ("aug" in t or "2026-08-30" in t or "cover" in t or "festival" in t):
                checks["2026-08-30 Kavya covered Rohan record"] = idx
    return checks


def match_beat2(memories):
    checks = {
        "2026-08-08 Meera covered Arjun": None,
        "2026-08-22 Meera covered Arjun": None,
        "2026-07-26 expired-window precedent (debt does not cancel)": None,
        "2026-09-27 no return Saturday logged record": None,
    }
    for idx, m in enumerate(memories, 1):
        t = m["text"].lower()
        if checks["2026-08-08 Meera covered Arjun"] is None:
            if "meera" in t and "arjun" in t and ("08-08" in t or "august 8" in t or "aug 8" in t or "first" in t):
                checks["2026-08-08 Meera covered Arjun"] = idx
        if checks["2026-08-22 Meera covered Arjun"] is None:
            if "meera" in t and "arjun" in t and ("08-22" in t or "august 22" in t or "aug 22" in t or "second" in t):
                checks["2026-08-22 Meera covered Arjun"] = idx
        if checks["2026-07-26 expired-window precedent (debt does not cancel)"] is None:
            if "expired" in t and ("cancel" in t or "debt" in t or "7 days" in t or "deadline" in t or "return" in t):
                checks["2026-07-26 expired-window precedent (debt does not cancel)"] = idx
        if checks["2026-09-27 no return Saturday logged record"] is None:
            if ("not logged" in t or "no return" in t) and ("arjun" in t or "saturday" in t or "sept" in t or "09-27" in t):
                checks["2026-09-27 no return Saturday logged record"] = idx
    return checks


def match_beat3(memories):
    checks = {
        "2026-06-14 Arjun/Sana verbal dispute (verbal not binding)": None,
        "2026-07-26 Arjun dispute (expired window / debt)": None,
        "Both distinct past Arjun disputes appear (pattern evidence)": None,
        "Aug 8 & Aug 22 covers OR 2026-09-27 no-return record (overdue evidence)": None,
    }
    pos_june = None
    pos_july = None
    for idx, m in enumerate(memories, 1):
        t = m["text"].lower()
        if pos_june is None:
            if "arjun" in t and "sana" in t and ("verbal" in t or "binding" in t or "app" in t or "june 14" in t or "06-14" in t):
                pos_june = idx
                checks["2026-06-14 Arjun/Sana verbal dispute (verbal not binding)"] = idx
        if pos_july is None:
            if "arjun" in t and ("rohan" in t or "expired" in t or "30" in t or "july 26" in t or "07-26" in t or "debt" in t):
                pos_july = idx
                checks["2026-07-26 Arjun dispute (expired window / debt)"] = idx
        if checks["Aug 8 & Aug 22 covers OR 2026-09-27 no-return record (overdue evidence)"] is None:
            if ("08-08" in t or "08-22" in t or "august 8" in t or "august 22" in t or "no return" in t or "09-27" in t or "not logged" in t) and ("arjun" in t or "meera" in t):
                checks["Aug 8 & Aug 22 covers OR 2026-09-27 no-return record (overdue evidence)"] = idx
    if pos_june is not None and pos_july is not None:
        checks["Both distinct past Arjun disputes appear (pattern evidence)"] = f"positions #{pos_june} and #{pos_july}"
    return checks


BEAT_MATCHERS = {
    "Beat 1: festival shift math": match_beat1,
    "Beat 2: expired swap window": match_beat2,
    "Beat 3: spot the pattern": match_beat3,
}


def run_checks():
    print(f"=== Checking Recall Quality on bank: '{os.environ['HINDSIGHT_BANK_ID']}' ===\n")
    all_passed = True
    beat_counts = {}

    for beat_name, prompt in DEMO_PROMPTS.items():
        print("==================================================")
        print(f"PROMPT: {beat_name}")
        print(f"Query: \"{prompt}\"")
        print("==================================================")

        # agent.gather_memories handles queries, round-robin merge, dedupe, and cap at 20
        memories = agent.gather_memories(prompt)
        count = len(memories)
        beat_counts[beat_name] = count
        print(f"Total memories in capped list: {count}\n")

        matcher = BEAT_MATCHERS[beat_name]
        results = matcher(memories)

        print("Verification Checklist:")
        beat_ok = True
        for requirement, pos in results.items():
            if pos is not None:
                tag = f"[FOUND #{pos}]" if isinstance(pos, int) else f"[FOUND {pos}]"
                print(f"  {tag:<18} {requirement}")
            else:
                print(f"  {'[MISSING]':<18} {requirement}")
                beat_ok = False
                all_passed = False

        print(f"\nFirst {min(8, count)} Recalled Memories (Ranked):")
        for i, m in enumerate(memories[:8], 1):
            print(f"  [{i}] ({m.get('type', 'memory')}): {m['text']}")

        print(f"\nBeat Result: {'PASS' if beat_ok else 'INCOMPLETE'}\n")

    print("==================================================")
    print("Memory Counts Summary:")
    for b_name, b_count in beat_counts.items():
        print(f"  - {b_name}: {b_count} (Cap: 20)")
    print(f"Overall Recall Status: {'PASS' if all_passed else 'NEEDS ATTENTION'}")
    print("==================================================")
    return all_passed


if __name__ == "__main__":
    run_checks()
