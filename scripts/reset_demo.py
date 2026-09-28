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


def reset_demo() -> str:
    timestamp = int(time.time())
    new_bank_id = f"brewline-demo-{timestamp}"

    # Set in env and write to .bank_id file
    os.environ["HINDSIGHT_BANK_ID"] = new_bank_id
    bank_file = ROOT / ".bank_id"
    bank_file.write_text(new_bank_id, encoding="utf-8")

    # Import memory & seed_data now so they pick up the new bank id
    import memory
    import seed_data

    print(f"Creating and seeding fresh demo bank: '{new_bank_id}'...")
    memory.ensure_bank()
    n = seed_data.seed()
    print(f"Successfully seeded {n} records into '{new_bank_id}'.")
    print(f"Active demo bank recorded in {bank_file.name}.")
    return new_bank_id


if __name__ == "__main__":
    reset_demo()
