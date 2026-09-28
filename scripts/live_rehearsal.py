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

# Ensure cache is strictly disabled and live keys are used
os.environ["DEMO_MOCK"] = "0"
os.environ["DISABLE_CACHE"] = "1"
os.environ["DEMO_CACHE_ONLY"] = "0"
os.environ["FORCE_MODEL"] = "qwen/qwen3.8-27b"

from streamlit.testing.v1 import AppTest
import memory
import seed_data


def run_rehearsal():
    print("================================================================================")
    print("STARTING LIVE REHEARSAL IN STREAMLIT UI (REAL MODEL, CACHE DISABLED)")
    print("Bank ID:", memory.get_bank_id())
    print("DISABLE_CACHE:", os.getenv("DISABLE_CACHE"))
    print("FORCE_MODEL:", os.getenv("FORCE_MODEL"))
    print("================================================================================\n")

    # -------------------------------------------------------------------------
    # Step 1: Beat 1 (Compare Mode ON)
    # -------------------------------------------------------------------------
    print("--------------------------------------------------------------------------------")
    print("BEAT 1: FESTIVAL SHIFT MATH (Compare Mode)")
    print("--------------------------------------------------------------------------------")
    at1 = AppTest.from_file("app.py", default_timeout=120)
    at1.run()
    assert not at1.exception, f"App init failed: {at1.exception}"

    beat1_btn = next((b for b in at1.button if "Beat 1" in b.label), None)
    assert beat1_btn is not None, "Beat 1 button not found"

    t0 = time.time()
    beat1_btn.click().run()
    t_beat1 = time.time() - t0
    assert not at1.exception, f"Beat 1 failed: {at1.exception}"

    last1 = at1.session_state.last
    off1 = last1["off"]
    on1 = last1["on"]

    print(f"Dispute: {last1['message']}")
    print(f"Timing: {t_beat1:.2f}s")
    print(f"Model used (off): {off1.get('model')}, from_cache: {off1.get('from_cache')}")
    print(f"Model used (on): {on1.get('model')}, from_cache: {on1.get('from_cache')}")
    print("\n[WITHOUT MEMORY ANSWER]:")
    print(off1["answer"])
    print("\n[WITH HINDSIGHT MEMORY ANSWER]:")
    print(on1["answer"])
    print("\n")

    # -------------------------------------------------------------------------
    # Step 2: Beat 2 (Expired Swap Window)
    # -------------------------------------------------------------------------
    print("--------------------------------------------------------------------------------")
    print("BEAT 2: EXPIRED SWAP WINDOW")
    print("--------------------------------------------------------------------------------")
    at2 = AppTest.from_file("app.py", default_timeout=120)
    at2.run()
    # Switch compare mode off for single-column memory focus
    at2.toggle[0].set_value(False).run()

    beat2_btn = next((b for b in at2.button if "Beat 2" in b.label), None)
    assert beat2_btn is not None, "Beat 2 button not found"

    t0 = time.time()
    beat2_btn.click().run()
    t_beat2 = time.time() - t0
    assert not at2.exception, f"Beat 2 failed: {at2.exception}"

    last2 = at2.session_state.last
    on2 = last2["on"]

    print(f"Dispute: {last2['message']}")
    print(f"Timing: {t_beat2:.2f}s")
    print(f"Model used: {on2.get('model')}, from_cache: {on2.get('from_cache')}")
    print("\n[WITH HINDSIGHT MEMORY ANSWER]:")
    print(on2["answer"])
    print("\n")

    # -------------------------------------------------------------------------
    # Step 3: Save Ruling for Beat 2
    # -------------------------------------------------------------------------
    print("--------------------------------------------------------------------------------")
    print("SAVING RULING TO HINDSIGHT MEMORY")
    print("--------------------------------------------------------------------------------")
    save_btn = next((b for b in at2.button if "Save ruling" in b.label), None)
    assert save_btn is not None, "Save ruling button not found"

    t0 = time.time()
    save_btn.click().run()
    t_save = time.time() - t0
    assert not at2.exception, f"Save ruling failed: {at2.exception}"

    print(f"Timing: {t_save:.2f}s")
    print(f"Saved dispute: {at2.session_state.saved_dispute}")
    print(f"Saved count: {at2.session_state.saved}")
    print("✓ Ruling retained in Hindsight live bank successfully.\n")

    # -------------------------------------------------------------------------
    # Step 4: Beat 3 (Spot the Pattern)
    # -------------------------------------------------------------------------
    print("--------------------------------------------------------------------------------")
    print("BEAT 3: SPOT THE PATTERN")
    print("--------------------------------------------------------------------------------")
    at3 = AppTest.from_file("app.py", default_timeout=120)
    at3.run()
    at3.toggle[0].set_value(False).run()

    beat3_btn = next((b for b in at3.button if "Beat 3" in b.label), None)
    assert beat3_btn is not None, "Beat 3 button not found"

    t0 = time.time()
    beat3_btn.click().run()
    t_beat3 = time.time() - t0
    assert not at3.exception, f"Beat 3 failed: {at3.exception}"

    last3 = at3.session_state.last
    on3 = last3["on"]

    print(f"Dispute: {last3['message']}")
    print(f"Timing: {t_beat3:.2f}s")
    print(f"Model used: {on3.get('model')}, from_cache: {on3.get('from_cache')}")
    print("\n[WITH HINDSIGHT MEMORY ANSWER]:")
    print(on3["answer"])
    print("\n")

    # -------------------------------------------------------------------------
    # Step 5: Reset the bank back cleanly
    # -------------------------------------------------------------------------
    print("================================================================================")
    print("CLEANING UP: RESETTING BANK 'brewline-demo-2' BACK TO ORIGINAL 18 SEED RECORDS")
    print("================================================================================")
    client = memory._get_client()
    target_bank = "brewline-demo-2"
    try:
        client.delete_bank(bank_id=target_bank)
        print(f"Deleted bank '{target_bank}'.")
    except Exception as e:
        print(f"Delete bank notice: {e}")

    memory.ensure_bank(target_bank)
    print(f"Re-creating and seeding 18 records into '{target_bank}'...")
    for i, (date, ctx, text) in enumerate(seed_data.RECORDS, 1):
        memory.retain(text, context=ctx, when=seed_data.D(date), bank_id=target_bank)
    print(f"✓ Done! Bank '{target_bank}' is cleanly reset and seeded with exactly 18 records.")
    print("================================================================================")


if __name__ == "__main__":
    run_rehearsal()
