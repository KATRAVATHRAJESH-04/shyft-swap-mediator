import os
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
os.environ["HINDSIGHT_BANK_ID"] = os.getenv("HINDSIGHT_BANK_ID", "brewline-swap-mediator")

from streamlit.testing.v1 import AppTest


def test_ui():
    print("================================================================================")
    print("STAGE 4: TESTING UI END-TO-END WITH REAL KEYS")
    print("================================================================================\n")

    # 1. Initial Load
    print("[1/4] Testing initial render...")
    at = AppTest.from_file("app.py", default_timeout=60)
    at.run()
    assert not at.exception, f"Initial load threw exception: {at.exception}"
    print("  ✓ App loaded without exceptions")
    print(f"  ✓ Found {len(at.button)} buttons on page")
    print(f"  ✓ Compare mode toggle value: {at.toggle[0].value}")

    # 2. Trigger Beat 1 via button
    print("\n[2/4] Testing Beat 1 button click...")
    # Find Beat 1 button
    beat1_btn = next((b for b in at.button if "Beat 1" in b.label), None)
    assert beat1_btn is not None, "Beat 1 button not found"
    beat1_btn.click().run()
    assert not at.exception, f"Beat 1 run threw exception: {at.exception}"
    
    # Check rendered elements
    chat_msgs = at.chat_message
    assert len(chat_msgs) > 0, "Expected user chat message to be rendered"
    print("  ✓ User message rendered:", chat_msgs[0].markdown[0].value[:60], "...")
    
    # Check subheaders for Compare Mode
    subheaders = [s.value for s in at.subheader]
    print(f"  ✓ Subheaders rendered: {subheaders}")
    assert "Without memory" in subheaders, "Missing 'Without memory' subheader"
    assert "With Hindsight memory" in subheaders, "Missing 'With Hindsight memory' subheader"
    
    # Check Priya's ruling text area
    text_areas = at.text_area
    assert len(text_areas) > 0, "Ruling text area not rendered"
    print("  ✓ Priya's ruling text area rendered with length:", len(text_areas[0].value), "chars")
    
    # Check Save ruling button
    save_btn = next((b for b in at.button if "Save ruling" in b.label), None)
    assert save_btn is not None, "Save ruling button not found"
    print("  ✓ 'Save ruling to memory' button is present")

    # 3. Test Compare Mode Toggle OFF & ON
    print("\n[3/4] Testing Compare mode toggle OFF & ON...")
    at.toggle[0].set_value(False).run()
    assert not at.exception, f"Toggle OFF run threw exception: {at.exception}"
    subheaders_off = [s.value for s in at.subheader]
    print(f"  ✓ Subheaders with Compare OFF: {subheaders_off}")
    assert "Without memory" not in subheaders_off, "'Without memory' should not be present when toggle is OFF"
    assert "With Hindsight memory" in subheaders_off, "'With Hindsight memory' should be present"

    # Flip back ON
    at.toggle[0].set_value(True).run()
    subheaders_on = [s.value for s in at.subheader]
    print(f"  ✓ Subheaders with Compare ON: {subheaders_on}")
    assert "Without memory" in subheaders_on, "'Without memory' should be present when toggle is ON"
    assert "With Hindsight memory" in subheaders_on, "'With Hindsight memory' should be present"

    # 4. Check Sidebar Memory Container
    print("\n[4/4] Testing sidebar memory panel rendering...")
    # Markdown entries rendered in sidebar
    markdowns = [m.value for m in at.sidebar.markdown]
    memory_bullets = [m for m in markdowns if m.startswith("- ")]
    print(f"  ✓ Sidebar contains {len(memory_bullets)} recalled memory bullets")
    assert len(memory_bullets) > 0, "Expected recalled memory bullets in sidebar"

    print("\n================================================================================")
    print("STAGE 4 UI TESTS PASSED COMPLETELY!")
    print("================================================================================")


if __name__ == "__main__":
    test_ui()
