import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Ensure UTF-8 output encoding on Windows console
if sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

os.environ["DEMO_MOCK"] = "0"
os.environ["HINDSIGHT_BANK_ID"] = os.getenv("HINDSIGHT_BANK_ID", "brewline-swap-mediator")

import agent
from prompts import DEMO_PROMPTS

KNOWN_STAFF_NAMES = {"Arjun", "Meera", "Rohan", "Kavya", "Sana", "Priya"}
OTHER_KNOWN_ENTITIES = {"Brewline", "Shyft", "Rao", "Iyer", "Shah", "Reddy", "Khan", "Nair"}
ALL_ALLOWED_NAMES = KNOWN_STAFF_NAMES | OTHER_KNOWN_ENTITIES

MONTH_MAP = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9, "october": 10, "oct": 10,
    "november": 11, "nov": 11, "december": 12, "dec": 12
}


def _norm(s):
    return s.replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-").replace("\u202f", " ")


def extract_and_normalize_dates(text):
    t = _norm(text)
    dates_found = []
    # 1. YYYY-MM-DD
    for m in re.finditer(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", t):
        norm = f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        dates_found.append((m.group(0), norm))
        
    # 2. Month DD, YYYY or Month DD
    m_pattern = r"\b(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?\b"
    for m in re.finditer(m_pattern, t, re.IGNORECASE):
        m_name = m.group(1).lower()
        month = MONTH_MAP[m_name]
        day = int(m.group(2))
        year = int(m.group(3)) if m.group(3) else 2026
        norm = f"{year:04d}-{month:02d}-{day:02d}"
        dates_found.append((m.group(0), norm))
        
    return dates_found


def compute_allowed_dates(memories):
    allowed = set()
    for m in memories:
        for d in re.findall(r"\b\d{4}-\d{2}-\d{2}\b", m["text"]):
            allowed.add(d)
            try:
                dt = datetime.strptime(d, "%Y-%m-%d")
                allowed.add((dt + timedelta(days=30)).strftime("%Y-%m-%d"))
            except Exception:
                pass
                
    base_dates = [
        "2026-06-01", "2026-06-02", "2026-06-12", "2026-06-14", "2026-06-21",
        "2026-07-19", "2026-07-20", "2026-07-26", "2026-08-01", "2026-08-05",
        "2026-08-08", "2026-08-22", "2026-08-30", "2026-09-03", "2026-09-10",
        "2026-09-13", "2026-09-27"
    ]
    for d in base_dates:
        allowed.add(d)
        dt = datetime.strptime(d, "%Y-%m-%d")
        allowed.add((dt + timedelta(days=30)).strftime("%Y-%m-%d"))
        
    today = datetime.now()
    allowed.add(today.strftime("%Y-%m-%d"))
    allowed.add((today + timedelta(days=7)).strftime("%Y-%m-%d"))
    return allowed


def check_word_count(text):
    words = text.split()
    count = len(words)
    status = "PASS" if count <= 170 else "FAIL"
    return f"{status} ({count} words, limit <= 170)"


def check_shape(text):
    t = text.lower()
    has_rec = "recommendation" in t or "1." in t or "verdict" in t
    has_evi = "evidence" in t or "2." in t or "records" in t
    has_tell = "what to tell" in t or "3." in t or "tell the employee" in t
    if has_rec and has_evi and has_tell:
        return "PASS"
    return "FAIL (missing 3-part shape)"


def check_attribution(text):
    record_terms = ["ruled", "ruling", "policy", "standing exception", "approved", "covered"]
    clauses = re.split(r"[\n.;!?]+", text)
    for c in clauses:
        c_lower = c.lower()
        if "you note" in c_lower or "you say" in c_lower:
            for term in record_terms:
                if term in c_lower:
                    return f"FAIL ('you note/say' combined with record term '{term}' in: '{c.strip()}')"
    return "PASS"


def check_app_mention_attribution(ans, prompt):
    ans_lower = ans.lower()
    prompt_has_app = "nothing in the app" in prompt.lower()
    # Check if answer says "you note nothing is logged" or mentions Priya noting the app
    matches = re.findall(r"\byou\s+(?:note|say)\b[^.\n]*\b(?:app|logged|record)\b", ans_lower)
    if matches and not prompt_has_app:
        return f"FAIL (answer attributes app state to Priya when dispute did not mention app: '{matches[0]}')"
    return "PASS"


def check_pattern_bullet(text, beat_name, is_memory_on=True):
    t = text.lower()
    has_pattern = bool(re.search(r"(?:^|\n)\s*[-*•]?\s*\**pattern:\**", t))
    if not is_memory_on:
        if has_pattern:
            return "FAIL (memory-OFF must not contain 'Pattern:')"
        return "PASS (no Pattern bullet expected when memory is OFF)"

    if "Beat 1" in beat_name:
        if has_pattern:
            return "FAIL (Beat 1 must not contain 'Pattern:')"
        return "PASS (no Pattern bullet in Beat 1)"
        
    m = re.search(r"(?:^|\n)\s*[-*•]?\s*\**pattern:\**([^\n]+)", text, re.I)
    if not m:
        if "Beat 3" in beat_name:
            return "FAIL (missing 'Pattern:' bullet in Beat 3)"
        return "PASS (no Pattern bullet in Beat 2)"
    content = m.group(1).strip()
    
    c_clean = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", content)
    c_clean = re.sub(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?\b", "", c_clean, flags=re.I)
    c_clean = re.sub(r"\b\d{4}\b", "", c_clean)
    words = [w for w in re.findall(r"\b[A-Za-z]+\b", c_clean) if w.lower() not in ["pattern"]]
    if len(words) < 8:
        return f"FAIL (Pattern bullet has only {len(words)} non-date word(s), required >= 8: '{content}')"
    return f"PASS (Pattern bullet has {len(words)} non-date words)"


def check_pattern_rohan_and_beat3(text, beat_name):
    m = re.search(r"(?:^|\n)\s*[-*•]?\s*\**pattern:\**([^\n]+)", text, re.I)
    if not m:
        return "PASS"
    content = m.group(1).lower()
    if ("rohan" in content or "06-21" in content or "june 21" in content) and "unreturned" in content:
        return f"FAIL (Pattern bullet calls Rohan swap 'unreturned': '{m.group(0).strip()}')"
    if "Beat 3" in beat_name and ("2026-06-14" not in content and "june 14" not in content and "06-14" not in content):
        return f"FAIL (Beat 3 Pattern bullet lacks 2026-06-14 ruling date: '{m.group(0).strip()}')"
    return "PASS"


def check_window_expired_date(text):
    t = _norm(text).lower()
    sentences = re.split(r"[\n.;!?]+", t)
    for s in sentences:
        if "expired" in s:
            for m in re.finditer(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", s):
                dt_str = f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
                if dt_str >= "2026-09-28":
                    return f"FAIL (claims window expired on/after 2026-09-28 in: '{s.strip()}')"
            for m_name in ["september", "sep", "sept"]:
                if m_name in s and ("29" in s or "30" in s):
                    return f"FAIL (claims window expired on/after 2026-09-28 in: '{s.strip()}')"
    return "PASS"


def check_july26_not_logged(text):
    for line in text.splitlines():
        l_lower = line.lower()
        has_july26 = "2026-07-26" in l_lower or "07-26" in l_lower or "july 26" in l_lower
        has_not_logged = "not logged" in l_lower or "has not" in l_lower
        if has_july26 and has_not_logged:
            return f"FAIL (mentions 07-26 together with 'not logged'/'has not': '{line.strip()}')"
    return "PASS"


def check_dates(text, memories):
    extracted = extract_and_normalize_dates(text)
    if not extracted:
        return "PASS (no dates cited)"
    allowed = compute_allowed_dates(memories)
    invalid = []
    for raw, norm in extracted:
        if norm not in allowed:
            invalid.append(f"'{raw}' -> {norm}")
    if invalid:
        return f"FAIL (dates not in allowed set: {', '.join(invalid)})"
    return f"PASS (all {len(extracted)} dates valid and allowed)"


def check_names(text, beat_name):
    req_names = []
    if "Beat 1" in beat_name:
        req_names = ["Kavya", "Rohan"]
    elif "Beat 2" in beat_name:
        req_names = ["Arjun", "Meera"]
    elif "Beat 3" in beat_name:
        req_names = ["Arjun", "Sana"]
    
    missing = [n for n in req_names if n.lower() not in text.lower()]
    if missing:
        return f"FAIL (missing expected employee name(s): {', '.join(missing)})"
        
    name_contexts = re.findall(r"\b(?:for|with|to|and|between|covered|claims?|owes?|rules?|ruled|staff|barista)\s+([A-Z][a-z]+)\b", text)
    unauthorized = []
    for candidate in name_contexts:
        if candidate not in ALL_ALLOWED_NAMES and candidate not in ["Saturday", "Saturdays", "Sunday", "Sundays", "Monday", "Friday", "August", "September", "June", "July"]:
            unauthorized.append(candidate)
            
    if unauthorized:
        return f"FAIL (unauthorized name(s) cited: {', '.join(set(unauthorized))})"
    return "PASS (valid staff names only)"


def check_off_forbidden_claims(text):
    t = text.lower()
    forbidden = ["not binding", "prior ruling", "prior rulings", "standing exception", "policy states", "brewline policy", "cafe policy", "café policy"]
    for f in forbidden:
        if f in t:
            return f"FAIL (memory-OFF contains forbidden claim '{f}')"
    for phrase in ["does not owe", "no shift is owed", "owes nothing", "no shift is due"]:
        matches = [m.start() for m in re.finditer(re.escape(phrase), t)]
        for idx in matches:
            prefix = t[max(0, idx - 40):idx]
            if "says" in prefix or "claims" in prefix or "argues" in prefix or "noted" in prefix:
                continue
            return f"FAIL (memory-OFF decides dispute with '{phrase}')"
    return "PASS"


def eval_beat1_on(ans):
    t = _norm(ans).lower()
    g1 = "PASS" if ("kavya" in t and ("right" in t or "owes two" in t or "owes 2" in t or "two shifts" in t or "two regular" in t)) else ("UNSURE" if "two" in t else "FAIL")
    g2 = "PASS" if (("2026-07-20" in t or "july 20" in t) and "festival" in t) else ("UNSURE" if "festival" in t else "FAIL")
    g3 = "PASS" if ("all staff" in t or "standing exception" in t or "all employees" in t or "all baristas" in t) else ("UNSURE" if "exception" in t else "FAIL")
    
    # Check 13: Beat 1 must say the window closes on or by 2026-09-29 (not expired)
    g4 = "FAIL (says 2026-09-29 window is expired)" if ("2026-09-29" in t and "expired" in t) else (
        "PASS" if ("2026-09-29" in t or "september 29" in t) and ("closes" in t or "by" in t or "on" in t or "window" in t) else "UNSURE (does not cite 2026-09-29 window)"
    )
    return [
        f"Says Kavya is right (Rohan owes two shifts): {g1}",
        f"Cites 2026-07-20 festival-day exception: {g2}",
        f"Mentions exception applies to all staff: {g3}",
        f"Window closes on or by 2026-09-29 (not expired): {g4}",
    ]


def eval_beat2_on(ans):
    t = _norm(ans).lower()
    g1 = "PASS" if (("debt" in t or "stands" in t or "valid" in t or "owes" in t) and ("two" in t or "2" in t) and "saturday" in t) else ("UNSURE" if "arjun owes" in t else "FAIL")
    g2 = "PASS" if (("sep" in t or "09-07" in t or "09-21" in t) or ("30 days" in t and ("window" in t or "passed" in t or "expired" in t))) else ("UNSURE" if "30 days" in t else "FAIL")
    g3 = "PASS" if (("2026-07-26" in t or "july 26" in t) and ("precedent" in t or "7 days" in t or "7-day" in t or "deadline" in t or "not cancel" in t or "ruling" in t or "debts do not expire" in t)) else ("UNSURE" if ("precedent" in t or "7 days" in t or "debts do not expire" in t) else "FAIL")
    g4 = "PASS" if (("2026-09-27" in t or "september 27" in t) and ("no return" in t or "not logged" in t or "unreturned" in t or "has not logged" in t)) else ("UNSURE" if ("not logged" in t or "no return" in t) else "FAIL")
    return [
        f"Says debt stands and Arjun owes Meera two Saturdays: {g1}",
        f"Notes both 30-day windows passed (Sep 7 and Sep 21): {g2}",
        f"Cites 2026-07-26 precedent and 7-day deadline: {g3}",
        f"Notes no return is logged as of 2026-09-27: {g4}",
    ]


def eval_beat3_on(ans):
    t = _norm(ans).lower()
    g1 = "PASS" if (("not binding" in t or "non-binding" in t or "not valid" in t) and ("arjun" in t)) else ("UNSURE" if "not binding" in t else "FAIL")
    has_june = "2026-06-14" in t or "june 14" in t or "june 12" in t
    has_july = "2026-07-26" in t or "july 26" in t
    g2 = "PASS" if (has_june and has_july) else ("UNSURE" if (has_june or has_july) else "FAIL")
    g3 = "PASS" if ("written" in t or "app" in t or "shyft" in t or "log" in t or "post" in t) else "FAIL"
    return [
        f"Says verbal claim is not binding and Arjun works the shift: {g1}",
        f"Cites both earlier Arjun disputes (2026-06-14 and 2026-07-26): {g2}",
        f"Recommends written confirmation for future swaps: {g3}",
    ]


def eval_off_answer(ans):
    t = ans.lower()
    no_records = "PASS" if ("no record" in t or "none available" in t or "cannot find" in t or "no information" in t or "don't settle" in t or "do not settle" in t) else ("UNSURE" if "records" in t else "FAIL")
    no_invented = "PASS" if not re.search(r"2026-\d{2}-\d{2}", ans) else "FAIL (invented specific date)"
    return [
        f"Honestly says records don't settle / none available: {no_records}",
        f"Does not invent specific dates or Brewline records: {no_invented}",
    ]


def print_checks_for_answer(beat_name, ans, prompt, memories, is_memory_on=True):
    print(f"  - Word count: {check_word_count(ans)}")
    print(f"  - 3-part shape: {check_shape(ans)}")
    print(f"  - Attribution rule: {check_attribution(ans)}")
    print(f"  - App mention attribution: {check_app_mention_attribution(ans, prompt)}")
    print(f"  - Window expiration date check: {check_window_expired_date(ans)}")
    print(f"  - July 26 check: {check_july26_not_logged(ans)}")
    print(f"  - Pattern bullet check: {check_pattern_bullet(ans, beat_name, is_memory_on=is_memory_on)}")
    print(f"  - Pattern Rohan/Beat 3 check: {check_pattern_rohan_and_beat3(ans, beat_name)}")
    print(f"  - Dates validation: {check_dates(ans, memories)}")
    print(f"  - Names check: {check_names(ans, beat_name)}")

    if not is_memory_on:
        print(f"  - Forbidden claims & non-decision: {check_off_forbidden_claims(ans)}")
        for item in eval_off_answer(ans):
            print(f"  - {item}")
    else:
        if "Beat 1" in beat_name:
            items = eval_beat1_on(ans)
        elif "Beat 2" in beat_name:
            items = eval_beat2_on(ans)
        else:
            items = eval_beat3_on(ans)
        for item in items:
            print(f"  - {item}")


def main():
    print("================================================================================")
    print("STAGE 3: LAST PASS REDUCED EVALUATION")
    print("================================================================================\n")

    # 1. Run each beat memory-ON once and memory-OFF once
    for beat_name, prompt in DEMO_PROMPTS.items():
        print("********************************************************************************")
        print(f"BEAT: {beat_name}")
        print(f"Dispute: \"{prompt}\"")
        print("********************************************************************************\n")

        # Memory OFF
        res_off = agent.respond(prompt, use_memory=False)
        print("--- [MEMORY OFF] ---")
        print(f"Model used: {res_off.get('model', 'unknown')}")
        print(f"Word count: {len(res_off['answer'].split())} words")
        print("\nFull Answer:")
        print(res_off["answer"])
        print("\nRubric Check (Memory OFF):")
        print_checks_for_answer(beat_name, res_off["answer"], prompt, [], is_memory_on=False)
        print("\n" + "-" * 60 + "\n")

        # Memory ON
        res_on = agent.respond(prompt, use_memory=True)
        print("--- [MEMORY ON] ---")
        print(f"Model used: {res_on.get('model', 'unknown')}")
        print(f"Recalled memories: {len(res_on['memories'])}")
        print("\nFull Answer:")
        print(res_on["answer"])
        print("\nRubric Check (Memory ON):")
        print_checks_for_answer(beat_name, res_on["answer"], prompt, res_on["memories"], is_memory_on=True)
        print("\n" + "=" * 80 + "\n")

    # 2. Run Beat 3 memory-ON three more times
    print("********************************************************************************")
    print("BEAT 3 MEMORY-ON: 3 ADDITIONAL REPEATED RUNS")
    print("********************************************************************************\n")
    beat3_prompt = DEMO_PROMPTS["Beat 3: spot the pattern"]
    for run_i in range(1, 4):
        print("================================================================================")
        print(f"BEAT 3 - REPEAT RUN {run_i}/3")
        print("================================================================================")
        res = agent.respond(beat3_prompt, use_memory=True)
        ans = res["answer"]
        model = res.get("model", "unknown")
        print(f"Model used: {model}")
        print(f"Word count: {len(ans.split())} words\n")
        print("Full Answer:")
        print(ans)
        print("\nRubric Check:")
        print_checks_for_answer("Beat 3: spot the pattern", ans, beat3_prompt, res["memories"], is_memory_on=True)
        print("\n")


if __name__ == "__main__":
    main()
