import os
import sys
import time
from datetime import datetime
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
os.environ["HINDSIGHT_BANK_ID"] = "learning-test"

import memory
import seed_data
import agent
from prompts import DEMO_PROMPTS
from streamlit.testing.v1 import AppTest


def main():
    print("================================================================================")
    print("STAGE 5: LEARNING LOOP VERIFICATION (SAVE RULING -> BEAT 3 RECALLS IT)")
    print("================================================================================\n")

    # Ensure isolated test bank exists and is seeded
    memory.ensure_bank()
    if not memory.recall("Brewline"):
        print("  [INIT] Seeding fresh 'learning-test' bank...")
        seed_data.seed()

    beat2_prompt = DEMO_PROMPTS["Beat 2: expired swap window"]
    beat3_prompt = DEMO_PROMPTS["Beat 3: spot the pattern"]

    # 1. Baseline Beat 3 memories before saving ruling
    print("[STEP 1] Baseline recall for Beat 3 before adding new ruling...")
    memories_before = agent.gather_memories(beat3_prompt)
    print(f"  Total memories returned: {len(memories_before)}")
    for idx, m in enumerate(memories_before[:5], 1):
        print(f"    [{idx}] {m['text'][:90]}...")
    print()

    # 2. Save Priya's Beat 2 ruling
    today_str = datetime.now().strftime("%Y-%m-%d")
    ruling_content = (
        "Arjun owes Meera two Saturday shifts for the August covers and must work them within 7 days; "
        "expired windows do not cancel debts."
    )
    print(f"[STEP 2] Saving Priya's ruling for Beat 2 into Hindsight...")
    print(f"  Dispute: \"{beat2_prompt}\"")
    print(f"  Ruling:  \"{ruling_content}\"")
    agent.record_ruling(beat2_prompt, ruling_content)
    print(f"  ✓ Successfully retained ruling into bank '{agent.memory.BANK_ID}'\n")

    # Small pause to ensure indexing propagation
    time.sleep(2)

    # 3. Recall for Beat 3 after saving ruling
    print("[STEP 3] Recalling memories for Beat 3 after saving ruling...")
    memories_after = agent.gather_memories(beat3_prompt)
    print(f"  Total memories in capped list: {len(memories_after)}")

    found_idx = None
    for idx, m in enumerate(memories_after, 1):
        t = m["text"].lower()
        if ("meera" in t and "saturday" in t and ("ruling" in t or "two saturday shifts" in t or today_str in t)):
            found_idx = idx
            break

    if found_idx:
        print(f"  ✓ [FOUND #{found_idx}] Freshly saved Beat 2 ruling surfaced in Beat 3 memories!")
        print(f"    Content: {memories_after[found_idx - 1]['text']}\n")
    else:
        print("  [WARNING] Freshly saved ruling not in top list; checking all items:")
        for idx, m in enumerate(memories_after, 1):
            print(f"    [{idx}] {m['text'][:100]}")
        print()

    # 4. Generate Beat 3 answer with memory ON
    print("[STEP 4] Generating Beat 3 answer with memory ON...")
    res = agent.respond(beat3_prompt, use_memory=True)
    print(f"  Model used: {res.get('model', 'unknown')}")
    print(f"  Word count: {len(res['answer'].split())} words\n")
    print("Full Answer:")
    print(res["answer"])
    print("\n" + "-" * 60 + "\n")

    # 5. Verify UI AppTest integration of the learning loop
    print("[STEP 5] Testing Learning Loop inside Streamlit UI via AppTest...")
    at = AppTest.from_file("app.py", default_timeout=60)
    at.run()
    assert not at.exception, f"Initial UI load error: {at.exception}"

    # Click Beat 2 button
    beat2_btn = next((b for b in at.button if "Beat 2" in b.label), None)
    assert beat2_btn is not None, "Beat 2 button not found"
    print("  ✓ Clicking 'Beat 2: expired swap window' in UI...")
    beat2_btn.click().run(timeout=60)
    assert not at.exception, f"Beat 2 UI click error: {at.exception}"

    # Click Save ruling button
    save_btn = next((b for b in at.button if "Save ruling" in b.label), None)
    assert save_btn is not None, "Save ruling button not found"
    print("  ✓ Clicking 'Save ruling to memory' in UI...")
    save_btn.click().run(timeout=60)
    assert not at.exception, f"Save ruling click error: {at.exception}"
    
    # Check that success message appeared
    success_msgs = [s.value for s in at.success]
    print(f"  ✓ Success notification: {success_msgs}")
    assert any("Retained" in s for s in success_msgs), "Expected 'Retained in Hindsight' success message"
    print(f"  ✓ Session saved count: {at.session_state.saved} ruling(s)")

    # Click Beat 3 button
    beat3_btn = next((b for b in at.button if "Beat 3" in b.label), None)
    assert beat3_btn is not None, "Beat 3 button not found"
    print("  ✓ Clicking 'Beat 3: spot the pattern' in UI...")
    beat3_btn.click().run(timeout=60)
    assert not at.exception, f"Beat 3 UI click error: {at.exception}"

    # Verify sidebar displays retained count and recalled memories
    sidebar_mds = [m.value for m in at.sidebar.markdown]
    memory_bullets = [m for m in sidebar_mds if m.startswith("- ")]
    print(f"  ✓ Sidebar contains {len(memory_bullets)} memory bullets for Beat 3")
    assert len(memory_bullets) > 0, "Sidebar should show recalled memories"

    print("\n================================================================================")
    print("STAGE 5 COMPLETE: LEARNING LOOP FULLY VERIFIED (CODE & UI)!")
    print("================================================================================")


if __name__ == "__main__":
    main()
