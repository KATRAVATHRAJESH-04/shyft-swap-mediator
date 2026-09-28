import io
import os
import sys
import time
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load .env
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

# Ensure real connections and isolated test bank before importing memory
os.environ["DEMO_MOCK"] = "0"
os.environ["HINDSIGHT_BANK_ID"] = "connection-test"


def check_env():
    print("--- 1. Checking Environment Variables ---")
    required = ["HINDSIGHT_BASE_URL", "HINDSIGHT_API_KEY", "GROQ_API_KEY"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        print(f"[FAIL] Missing required variable(s) in .env: {', '.join(missing)}")
        return False
    print("[PASS] All required environment variables are set (values hidden).")
    return True


def check_hindsight():
    print("\n--- 2. Checking Hindsight (ensure_bank, retain, recall) ---")
    try:
        import memory
    except Exception as e:
        print(f"[FAIL] Failed to import memory module: {e}")
        return False

    # 2a. ensure_bank()
    buf = io.StringIO()
    try:
        with redirect_stdout(buf), redirect_stderr(buf):
            memory.ensure_bank()
        warning = buf.getvalue().strip()
        if warning:
            print(f"[INFO] ensure_bank notice: {warning}")
        print("[PASS] memory.ensure_bank() completed.")
    except Exception as e:
        print(f"[FAIL] memory.ensure_bank() raised: {e}")
        return False

    # 2b. retain() test record
    test_record = "Connection test: the café's test employee Zed covered a shift on 2026-01-01"
    try:
        print(f"Retaining test record: \"{test_record}\"")
        memory.retain(test_record, context="connection_test")
        print("[PASS] memory.retain() succeeded.")
    except Exception as e:
        print(f"[FAIL] memory.retain() failed: {e}")
        return False

    # 2c. recall() with retry up to 5 times (2-second wait)
    query = "Zed shift cover"
    print(f"Recalling with query: \"{query}\" (up to 5 attempts, 2s interval)...")
    found = False
    last_results = []
    for attempt in range(1, 6):
        try:
            results = memory.recall(query)
            last_results = results
            for r in results:
                if "zed" in r.get("text", "").lower():
                    print(f"[PASS] Found match on attempt {attempt}: \"{r['text']}\"")
                    found = True
                    break
            if found:
                break
        except Exception as e:
            print(f"[WARN] Attempt {attempt} error: {e}")
        time.sleep(2)

    if not found:
        print(f"[FAIL] Recall did not return 'Zed' within 5 attempts. Last results: {last_results}")
        return False

    return True


def check_groq():
    print("\n--- 3. Checking Groq Models ---")
    try:
        from groq import Groq
    except ImportError:
        print("[FAIL] groq package is not installed.")
        return False

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("[FAIL] GROQ_API_KEY is missing.")
        return False

    client = Groq(api_key=api_key)
    models = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]
    all_ok = True

    for model in models:
        print(f"Testing model: {model} (max_tokens=200)...")
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Say hello in one short sentence."}],
                max_tokens=200,
                temperature=0.2,
            )
            choice = r.choices[0]
            reply = (choice.message.content or "").strip()
            finish_reason = getattr(choice, "finish_reason", "unknown")
            print(f"[PASS] {model} responded successfully:")
            print(f"       reply: \"{reply}\"")
            print(f"       finish_reason: {finish_reason}")
        except Exception as e:
            print(f"[FAIL] {model} call failed: {e}")
            all_ok = False

    return all_ok


def main():
    print("=== Connection Checker: Hindsight & Groq ===")
    env_ok = check_env()
    if not env_ok:
        print("\nAborting further checks until .env is properly configured.")
        sys.exit(1)

    hindsight_ok = check_hindsight()
    groq_ok = check_groq()

    print("\n=== Summary ===")
    print(f"Environment: {'PASS' if env_ok else 'FAIL'}")
    print(f"Hindsight:   {'PASS' if hindsight_ok else 'FAIL'}")
    print(f"Groq:        {'PASS' if groq_ok else 'FAIL'}")

    if not (env_ok and hindsight_ok and groq_ok):
        sys.exit(1)


if __name__ == "__main__":
    main()
