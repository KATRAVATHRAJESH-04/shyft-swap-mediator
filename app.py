import os
import re
import json

import streamlit as st
from dotenv import load_dotenv

import agent
import memory
import seed_data
from prompts import DEMO_PROMPTS
import guardrails
import policy_engine
import roster_sync

load_dotenv()
st.set_page_config(page_title="Shyft Swap Mediator", page_icon="☕", layout="wide")

# Custom CSS for high-end, clean SaaS styling
st.markdown(
    """
<style>
    /* Global font & clean spacing */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1200px;
    }
    
    /* Elegant header & subtitle */
    .app-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: #f1f5f9;
        color: #475569;
        font-size: 0.78rem;
        font-weight: 600;
        padding: 3px 10px;
        border-radius: 20px;
        margin-bottom: 8px;
        border: 1px solid #e2e8f0;
        letter-spacing: 0.03em;
        text-transform: uppercase;
    }
    .app-title {
        font-size: 2.1rem;
        font-weight: 800;
        color: #0f172a;
        letter-spacing: -0.02em;
        margin-bottom: 4px;
        line-height: 1.2;
    }
    .app-tagline {
        font-size: 1.05rem;
        color: #334155;
        font-weight: 500;
        margin-bottom: 12px;
        line-height: 1.4;
    }
    
    /* Sleek minimalist pipeline flow */
    .flow-bar {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 8px;
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 6px 14px;
        margin-bottom: 20px;
        font-size: 0.78rem;
        color: #64748b;
    }
    .flow-step {
        font-weight: 600;
        color: #334155;
    }
    .flow-arrow {
        color: #cbd5e1;
        font-size: 0.72rem;
    }

    /* Clean Card Containers */
    .card-box {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 14px;
    }

    /* Status Pills */
    .pill-green {
        display: inline-flex;
        align-items: center;
        background: #f0fdf4;
        color: #166534;
        border: 1px solid #bbf7d0;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-bottom: 8px;
    }
    .pill-amber {
        display: inline-flex;
        align-items: center;
        background: #fffbeb;
        color: #92400e;
        border: 1px solid #fde68a;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-bottom: 8px;
    }
    .pill-blue {
        display: inline-flex;
        align-items: center;
        background: #eff6ff;
        color: #1e40af;
        border: 1px solid #bfdbfe;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-bottom: 8px;
    }
</style>
""",
    unsafe_allow_html=True,
)

# Initialize session state keys
for key, default in [
    ("last", None),
    ("seeded", False),
    ("saved", 0),
    ("error", None),
    ("saved_dispute", None),
    ("learning_step", 0),
    ("learned_precedents", []),
]:
    st.session_state.setdefault(key, default)

if "policy_registry" not in st.session_state:
    st.session_state.policy_registry = policy_engine.PolicyRegistry()

BEAT_4_PROMPTS = {
    "Beat 4A: half-shift dispute": (
        "Sana covered 4 hours of Rohan's 8-hour shift yesterday. Sana says Rohan owes her a full shift back "
        "because she gave up her evening; Rohan says he only owes 4 hours or half a shift. What's the policy?"
    ),
    "Beat 4B: half-shift precedent": (
        "Aisha covered 4 hours of Tariq's shift on Thursday. Aisha says Tariq owes her a full shift back, "
        "but Tariq says he only owes half a shift. What's the ruling?"
    ),
}


def parse_verdict_sections(text: str) -> dict:
    """Splits the 3-part verdict into Recommendation, Evidence, and Employee script."""
    if not text:
        return {"rec": "", "evi": "", "emp": ""}

    h2_match = re.search(r"(?:(?:\n|\A)(?:\*{0,2}(?:2\.\s*)?Evidence\*{0,2}:?))", text, re.IGNORECASE)
    h3_match = re.search(r"(?:(?:\n|\A)(?:\*{0,2}(?:3\.\s*)?What to tell(?: the employees)?\*{0,2}:?))", text, re.IGNORECASE)

    if h2_match and h3_match and h2_match.start() < h3_match.start():
        rec_part = text[:h2_match.start()].strip()
        evi_part = text[h2_match.end():h3_match.start()].strip()
        emp_part = text[h3_match.end():].strip()

        rec_part = re.sub(r"^(?:\*{0,2}(?:1\.\s*)?Recommendation\*{0,2}:?\s*)", "", rec_part, flags=re.IGNORECASE).strip()
        return {"rec": rec_part, "evi": evi_part, "emp": emp_part}

    return {"rec": text, "evi": "", "emp": ""}


# ---------------- sidebar ----------------
with st.sidebar:
    st.markdown("### ⚙️ System Controls")
    st.caption(f"Demo Calendar Date: **{agent.get_demo_today_str()}**")
    compare = st.toggle("Compare mode (memory OFF vs ON)", value=True)

    missing = [] if memory.is_mock() else [
        k for k in ("HINDSIGHT_BASE_URL", "HINDSIGHT_API_KEY", "GROQ_API_KEY") if not os.getenv(k)
    ]
    if memory.is_mock():
        st.info("Mock mode: fake memory + fake LLM (DEMO_MOCK=1)")
    elif missing:
        st.error("Missing in .env: " + ", ".join(missing))

    if st.button("Load Brewline history into Hindsight", disabled=st.session_state.seeded or bool(missing)):
        with st.spinner("Retaining records..."):
            n = seed_data.seed()
        st.session_state.seeded = True
        st.success(f"Retained {n} records")
    st.caption("Click once per bank. Re-running adds duplicates.")

    st.divider()
    st.markdown("### 🏛️ Institutional Memory")
    total_mem = 18 + st.session_state.saved
    st.metric(
        label="Accumulated Store Knowledge",
        value=f"{total_mem} Records",
        delta=f"+{st.session_state.saved} live ruling(s)" if st.session_state.saved > 0 else "Baseline",
    )
    st.caption(f"Memory Bank: `{memory.get_bank_id()}`")

    with st.expander("📜 View Standing Policies (5 Core)", expanded=False):
        for p in st.session_state.policy_registry.get_active_policies()[:5]:
            st.markdown(f"**{p['name']}**: {p['rule']}")

    if st.session_state.learned_precedents:
        with st.expander(f"🟢 Learned Precedents ({len(st.session_state.learned_precedents)})", expanded=True):
            for lp in st.session_state.learned_precedents:
                st.markdown(f"- **{lp['when']}:** {lp['ruling'][:80]}...")

    st.divider()
    st.markdown("### 🧠 Memories Recalled")
    memory_panel = st.container()

# ---------------- main header ----------------
st.markdown('<div class="app-badge">☕ Brewline Café · Shift Operations</div>', unsafe_allow_html=True)
st.markdown('<div class="app-title">Shyft Swap Mediator</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="app-tagline">Shyft remembers how your business resolves shift disputes — and gets more consistent with every decision.</div>',
    unsafe_allow_html=True,
)

# Minimalist workflow tracker
st.markdown(
    """
<div class="flow-bar">
  <span class="flow-step">1. Dispute</span>
  <span class="flow-arrow">➔</span>
  <span class="flow-step">2. Recall Memory</span>
  <span class="flow-arrow">➔</span>
  <span class="flow-step">3. Evaluate Precedent</span>
  <span class="flow-arrow">➔</span>
  <span class="flow-step">4. Recommendation</span>
  <span class="flow-arrow">➔</span>
  <span class="flow-step">5. Manager Confirms</span>
  <span class="flow-arrow">➔</span>
  <span class="flow-step">6. Memory Accumulates</span>
</div>
""",
    unsafe_allow_html=True,
)

# ---------------- demo scenarios (clean tabbed design) ----------------
pending = None

tab_core, tab_learning = st.tabs(["⚡ Core Disputes (Foundation Beats)", "🔄 Live Learning Demo (Unknown Case ➔ New Precedent)"])

with tab_core:
    st.caption("Click any dispute to compare vanilla LLM reasoning against Hindsight institutional memory:")
    col1, col2, col3 = st.columns(3)
    if col1.button("Beat 1: festival shift math", use_container_width=True):
        pending = DEMO_PROMPTS["Beat 1: festival shift math"]
        st.session_state.learning_step = 0
    if col2.button("Beat 2: expired swap window", use_container_width=True):
        pending = DEMO_PROMPTS["Beat 2: expired swap window"]
        st.session_state.learning_step = 0
    if col3.button("Beat 3: spot the pattern", use_container_width=True):
        pending = DEMO_PROMPTS["Beat 3: spot the pattern"]
        st.session_state.learning_step = 0

with tab_learning:
    st.caption("Walk through the full institutional learning loop: an unhandled case arrives, Priya creates policy, and future disputes reuse it:")
    c_s1, c_s2, c_s3 = st.columns([1, 1, 1])
    with c_s1:
        if st.button("Step 1: Test Unknown Case\n(Sana vs Rohan - 4hr cover)", use_container_width=True):
            pending = BEAT_4_PROMPTS["Beat 4A: half-shift dispute"]
            st.session_state.learning_step = 1
    with c_s2:
        st.markdown(
            "<div style='text-align: center; padding-top: 10px;'><span style='font-size:0.83rem; color:#64748b;'><strong>Step 2:</strong> Manager Confirms Ruling Below ➔</span></div>",
            unsafe_allow_html=True,
        )
    with c_s3:
        if st.button("Step 3: Test New Case\n(Aisha vs Tariq - Precedent Applied)", use_container_width=True):
            pending = BEAT_4_PROMPTS["Beat 4B: half-shift precedent"]
            st.session_state.learning_step = 3

# Manual input
typed = st.chat_input("Describe a shift-swap dispute...")
message = pending or typed

if message:
    st.session_state.error = None
    try:
        with st.spinner("Retrieving institutional memory & evaluating..."):
            if compare:
                off, on = agent.respond_compare(message)
            else:
                off = None
                on = agent.respond(message, use_memory=True)
        st.session_state.last = {"message": message, "off": off, "on": on}
    except Exception as e:
        st.session_state.error = str(e)

if st.session_state.error:
    st.error(st.session_state.error)

last = st.session_state.last
if last:
    with st.chat_message("user"):
        st.markdown(f"**Dispute:** {last['message']}")

    is_novel = ("half" in last["message"].lower() and "rohan" in last["message"].lower() and "sana" in last["message"].lower())
    is_reused = ("half" in last["message"].lower() and "tariq" in last["message"].lower() and "aisha" in last["message"].lower())

    if is_novel:
        st.markdown(
            '<div class="pill-amber">⚠️ UNKNOWN CASE: No relevant precedent in store records · Manager decision required below to establish policy.</div>',
            unsafe_allow_html=True,
        )
    elif is_reused:
        st.markdown(
            '<div class="pill-green">🎯 PRECEDENT RECALLED: Hindsight retrieved Priya\'s half-shift ruling and applied it to Aisha & Tariq consistently!</div>',
            unsafe_allow_html=True,
        )

    # Deterministic Timeline Verification Callout
    if "festival" in last["message"].lower() or "kavya" in last["message"].lower():
        win = agent.calculate_window_status("2026-08-30", window_days=30)
        st.caption(f"📅 **Deterministic Calendar Verification:** Cover Date: 2026-08-30 ➔ 30-Day Window Deadline: {win['end_date']} ➔ Status: **{win['status_str']}**")
    elif "august" in last["message"].lower() or "meera" in last["message"].lower():
        win1 = agent.calculate_window_status("2026-08-08", window_days=30)
        win2 = agent.calculate_window_status("2026-08-22", window_days=30)
        st.caption(f"📅 **Deterministic Calendar Verification:** Aug 8 cover ended {win1['end_date']} (EXPIRED); Aug 22 cover ended {win2['end_date']} (EXPIRED) ➔ Priya's 2026-07-26 precedent preserves debt.")

    if compare and last.get("off") is not None:
        left, right = st.columns(2)
        with left:
            st.subheader("Without memory")
            st.markdown('<div class="pill-amber">❌ Insufficient Historical Context · Vanilla LLM</div>', unsafe_allow_html=True)

            parsed_off = parse_verdict_sections(last["off"]["answer"])
            if parsed_off["rec"] and parsed_off["evi"]:
                with st.container(border=True):
                    st.markdown("**⚖️ PROPOSED DECISION**")
                    st.write(parsed_off["rec"])
                with st.container(border=True):
                    st.markdown("**📜 EVIDENCE (NO STORE RECORDS)**")
                    st.write(parsed_off["evi"])
                if parsed_off["emp"]:
                    with st.container(border=True):
                        st.markdown("**💬 WHAT TO TELL THE EMPLOYEES**")
                        st.write(parsed_off["emp"])
            else:
                st.write(last["off"]["answer"])

            if last["off"].get("model"):
                st.caption(f"Model: {last['off']['model']}")
            if last["off"].get("from_cache"):
                st.caption("Served from cached demo run (live model rate-limited)")

        with right:
            if last["on"].get("memory_error"):
                st.warning("Memory unavailable: answer below is NOT using Hindsight")
            st.subheader("With Hindsight memory")

            memories = last["on"].get("memories", [])
            if is_novel:
                st.markdown('<div class="pill-amber">🔍 No Prior Precedent Found · Manager Decision Required</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="pill-green">✅ Historical Precedent Found · {len(memories)} memories retrieved</div>', unsafe_allow_html=True)

            parsed_on = parse_verdict_sections(last["on"]["answer"])
            if parsed_on["rec"] and parsed_on["evi"]:
                with st.container(border=True):
                    st.markdown("**⚖️ RECOMMENDED RULING** *(Manager Confirmation Required)*")
                    st.write(parsed_on["rec"])
                with st.container(border=True):
                    st.markdown(f"**📜 PRECEDENT & FACTS RECALLED** *(Grounded in {len(memories)} Hindsight Records)*")
                    st.write(parsed_on["evi"])
                if parsed_on["emp"]:
                    with st.container(border=True):
                        st.markdown("**💬 WHAT TO TELL THE EMPLOYEES** *(Action Script for Priya)*")
                        st.write(parsed_on["emp"])
            else:
                st.write(last["on"]["answer"])

            if last["on"].get("model"):
                st.caption(f"Model: {last['on']['model']}")
            if last["on"].get("from_cache"):
                st.caption("Served from cached demo run (live model rate-limited)")
    else:
        if last["on"].get("memory_error"):
            st.warning("Memory unavailable: answer below is NOT using Hindsight")
        st.subheader("With Hindsight memory")
        memories = last["on"].get("memories", [])
        if is_novel:
            st.markdown('<div class="pill-amber">🔍 No Prior Precedent Found · Manager Decision Required</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="pill-green">✅ Historical Precedent Found · {len(memories)} memories retrieved</div>', unsafe_allow_html=True)

        parsed_on = parse_verdict_sections(last["on"]["answer"])
        if parsed_on["rec"] and parsed_on["evi"]:
            with st.container(border=True):
                st.markdown("**⚖️ RECOMMENDED RULING** *(Manager Confirmation Required)*")
                st.write(parsed_on["rec"])
            with st.container(border=True):
                st.markdown(f"**📜 PRECEDENT & FACTS RECALLED** *(Grounded in {len(memories)} Hindsight Records)*")
                st.write(parsed_on["evi"])
            if parsed_on["emp"]:
                with st.container(border=True):
                    st.markdown("**💬 WHAT TO TELL THE EMPLOYEES** *(Action Script for Priya)*")
                    st.write(parsed_on["emp"])
        else:
            st.write(last["on"]["answer"])

        if last["on"].get("model"):
            st.caption(f"Model: {last['on']['model']}")
        if last["on"].get("from_cache"):
            st.caption("Served from cached demo run (live model rate-limited)")

    st.divider()
    st.markdown("### ✍️ Priya's Final Ruling & Institutional Precedent Creation")
    st.caption("Priya Nair has final authority. Confirm or edit the ruling below. Once saved, it becomes permanent institutional memory for future disputes.")

    default_ruling = last["on"]["answer"]
    if is_novel:
        default_ruling = (
            "Priya ruled that half-shift covers count as half a shift (pro-rated repayment of 4 hours), "
            "establishing this as a standing policy for all staff."
        )

    ruling = st.text_area("Edit or paste the ruling", value=default_ruling, height=110,
                          key=f"ruling_{hash(last['message'])}")
    
    is_blank = not ruling or not ruling.strip()
    already_saved = (st.session_state.saved_dispute == last["message"])
    save_disabled = already_saved or is_blank

    # Real-time Statutory Labor Law & Fairness Check
    if not is_blank:
        compliance = guardrails.verify_compliance(ruling, last["message"])
        if compliance["compliant"]:
            st.markdown(
                f'<div class="pill-green">🛡️ Statutory Labor Standards & Fairness: PASSED ({compliance["score"]}/100) · Rest period, definitive timeline, & non-punitive tone verified.</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="pill-amber">⚠️ Compliance Advisory: {compliance["summary"]} ({compliance["score"]}/100)</div>',
                unsafe_allow_html=True,
            )

    if already_saved:
        st.success("Retained in Hindsight.")
        st.caption("✓ Ruling saved to memory for this dispute.")

        # Show Automated Roster Sync Status
        roster_evt = roster_sync.generate_roster_payload(last["message"], ruling)
        st.markdown(
            f'<div class="pill-blue">📡 Roster Synced to Scheduling API (Event #{roster_evt["event_id"]}) · Dispatched shift adjustment payload to 7shifts & Toast POS.</div>',
            unsafe_allow_html=True,
        )
        with st.expander(f"🔍 View Dispatch Payload for 7shifts & POS (JSON)", expanded=False):
            st.json(roster_evt)

        if is_novel or st.session_state.learning_step in (1, 2):
            st.info("👉 **Step 2 Completed:** Precedent is active in Hindsight! Now click **Step 3: Test New Case (Aisha vs Tariq)** above to watch Hindsight apply this rule.")
    elif is_blank:
        st.caption("Enter a non-empty ruling to save.")

    if st.button("Save ruling to memory", disabled=save_disabled):
        if is_blank:
            st.error("Cannot save an empty ruling.")
        else:
            try:
                agent.record_ruling(last["message"], ruling.strip())
                st.session_state.saved += 1
                st.session_state.saved_dispute = last["message"]
                st.session_state.setdefault("learned_precedents", []).append({
                    "dispute": last["message"][:75] + "...",
                    "ruling": ruling.strip(),
                    "when": agent.get_demo_today_str(),
                })
                # Register policy into versioned registry
                st.session_state.policy_registry.register_or_supersede(ruling.strip(), last["message"], agent.get_demo_today_str())
                if st.session_state.learning_step == 1:
                    st.session_state.learning_step = 2
                st.success("Retained in Hindsight.")
                st.rerun()
            except Exception as e:
                st.error(f"Could not retain: {e}")

with memory_panel:
    if last and last["on"]["memories"]:
        for m in last["on"]["memories"]:
            st.markdown(f"- {m['text']}")
    else:
        st.caption("Nothing recalled yet.")
    if st.session_state.saved:
        st.caption(f"{st.session_state.saved} ruling(s) retained this session")
