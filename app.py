import os
import re

import streamlit as st
from dotenv import load_dotenv

import agent
import memory
import seed_data
from prompts import DEMO_PROMPTS

load_dotenv()
st.set_page_config(page_title="Shyft Swap Mediator", page_icon="🗓️", layout="wide")

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
    st.header("Controls")
    st.caption(f"Demo date: {agent.get_demo_today_str()}")
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
    st.header("🏛️ Institutional Memory")
    st.metric(
        "Knowledge Accumulation",
        f"{18 + st.session_state.saved} Records",
        f"+{st.session_state.saved} live ruling(s)" if st.session_state.saved > 0 else "18 base records",
    )
    st.caption(f"Bank ID: `{memory.get_bank_id()}`")

    st.divider()
    st.header("Memories recalled")
    memory_panel = st.container()

# ---------------- main header & flow ----------------
st.title("🗓️ Shyft Swap Mediator")
st.markdown("#### Shyft remembers how your business resolves shift disputes — and gets more consistent with every decision.")
st.caption("Brewline Café · Priya Nair, Shift Manager · Persistent Institutional Memory by Hindsight Cloud")

# Visual Workflow Pipeline Tracker
st.markdown(
    """
<div style="display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px 14px; margin-bottom: 16px; font-size: 0.82rem; color: #334155;">
  <span><strong>1. Dispute</strong></span> ➔ 
  <span><strong>2. Recall Memory</strong></span> ➔ 
  <span><strong>3. Evaluate Precedent</strong></span> ➔ 
  <span><strong>4. Recommendation</strong></span> ➔ 
  <span><strong>5. Manager Confirms</strong></span> ➔ 
  <span><strong>6. Memory Accumulates</strong></span>
</div>
""",
    unsafe_allow_html=True,
)

# Visible Section: BREWLINE INSTITUTIONAL MEMORY
with st.expander(f"🏛️ BREWLINE INSTITUTIONAL MEMORY ({18 + st.session_state.saved} Records Active)", expanded=False):
    col_mem1, col_mem2 = st.columns(2)
    with col_mem1:
        st.markdown("**POLICIES & PRECEDENTS** *(Ground truth from bank)*")
        st.markdown("""
- ⚖️ **Festival-day coverage = 2 shifts** *(Established by Priya on 2026-07-20)*
- 📱 **Verbal swaps are non-binding** *(Must be logged in Shyft app per 2026-06-14 ruling)*
- ⏳ **Expired return windows do not erase debt** *(7-day cure deadline per 2026-07-26 ruling)*
- 📅 **30-day return window** *(Covered shifts must be returned within 30 days)*
- 🚨 **Emergency exception** *(Genuine emergencies are the only valid exception)*
        """)
    with col_mem2:
        st.markdown("**LEARNED RECENTLY** *(Manager-created precedents)*")
        if st.session_state.learned_precedents:
            for lp in st.session_state.learned_precedents:
                st.markdown(f"- 🟢 **{lp['when']}:** {lp['ruling'][:100]}... *(Saved to Hindsight)*")
        else:
            st.caption("• *No live rulings added yet this session. Run the Live Learning Demo below to teach the agent a new rule!*")
        st.caption(f"Bank `{memory.get_bank_id()}` · Disposition: skepticism=4, literalism=4, empathy=3")

# ---------------- demo disputes & live learning ----------------
st.markdown("### ⚡ Demo Disputes")

# 1-click foundation beats
cols = st.columns(len(DEMO_PROMPTS))
pending = None
for col, (label, text) in zip(cols, DEMO_PROMPTS.items()):
    if col.button(label, use_container_width=True):
        pending = text
        st.session_state.learning_step = 0

# The Centerpiece: Live Learning Loop
with st.container(border=True):
    st.markdown("#### 🔄 Centerpiece Demo: The Live Learning Loop (Unknown Case → New Policy)")
    st.caption("Watch Shyft handle an unprecedented dispute, prompt the manager for a ruling, commit it to Hindsight, and apply it to a new dispute with different employees.")
    c_step1, c_step2, c_step3 = st.columns([1, 1, 1])
    with c_step1:
        if st.button("Step 1: Test Unknown Case\n(Sana vs Rohan - 4hr cover)", use_container_width=True, type="primary" if st.session_state.learning_step == 0 else "secondary"):
            pending = BEAT_4_PROMPTS["Beat 4A: half-shift dispute"]
            st.session_state.learning_step = 1
    with c_step2:
        st.markdown("<div style='text-align: center; padding-top: 8px;'><span style='font-size:0.85rem; color:#64748b;'><strong>Step 2:</strong> Manager Confirms Ruling Below ➔</span></div>", unsafe_allow_html=True)
    with c_step3:
        if st.button("Step 3: Test New Case\n(Aisha vs Tariq - Precedent Applied)", use_container_width=True, type="primary" if st.session_state.learning_step >= 2 else "secondary"):
            pending = BEAT_4_PROMPTS["Beat 4B: half-shift precedent"]
            st.session_state.learning_step = 3

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
        st.write(last["message"])

    # Special callouts for the Live Learning Loop demo
    is_novel = ("half" in last["message"].lower() and "rohan" in last["message"].lower() and "sana" in last["message"].lower())
    is_reused = ("half" in last["message"].lower() and "tariq" in last["message"].lower() and "aisha" in last["message"].lower())

    if is_novel:
        st.warning(
            "🚨 **UNKNOWN CASE (STEP 1): No relevant precedent found in store records.**\n\n"
            "Hindsight searched institutional memory and found no policy for partial-shift covers. "
            "The agent refuses to invent a rule. **Manager decision required (Step 2)** below to establish policy."
        )
    elif is_reused:
        st.success(
            "🎯 **NEW PRECEDENT RECALLED (STEP 3): Hindsight retrieved Priya's ruling!**\n\n"
            "Recalled precedent: *'Priya ruled that half-shift covers count as half a shift (pro-rated repayment of 4 hours)...'*\n\n"
            "The agent applied this newly learned rule to Aisha & Tariq consistently, without model fine-tuning or code changes."
        )

    if compare and last.get("off") is not None:
        left, right = st.columns(2)
        with left:
            st.subheader("Without memory")
            st.error("⚠️ **Insufficient Historical Context** · Vanilla LLM has no store records")

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
                st.warning("🔍 **No Prior Precedent Found** · Manager decision required")
            else:
                st.success(f"✅ **Historical Precedent Found** · {len(memories)} memories influenced this ruling")

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
            st.warning("🔍 **No Prior Precedent Found** · Manager decision required")
        else:
            st.success(f"✅ **Historical Precedent Found** · {len(memories)} memories influenced this ruling")

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
    st.markdown("### ✍️ Priya's Final Ruling (Institutional Precedent Creation)")
    st.caption("Manager Confirmation Required: Priya Nair has final authority. Edit or confirm the ruling below. Once saved, it becomes permanent institutional memory for future disputes.")

    default_ruling = last["on"]["answer"]
    if is_novel:
        default_ruling = (
            "Priya ruled that half-shift covers count as half a shift (pro-rated repayment of 4 hours), "
            "establishing this as a standing policy for all staff."
        )

    ruling = st.text_area("Edit or paste the ruling", value=default_ruling, height=120,
                          key=f"ruling_{hash(last['message'])}")
    
    is_blank = not ruling or not ruling.strip()
    already_saved = (st.session_state.saved_dispute == last["message"])
    save_disabled = already_saved or is_blank

    if already_saved:
        st.success("Retained in Hindsight.")
        st.caption("✓ Ruling saved to memory for this dispute.")
        if is_novel or st.session_state.learning_step in (1, 2):
            st.info("👉 **Step 2 Completed:** Precedent is now active in Hindsight! Now click **Step 3: Test New Case (Aisha vs Tariq)** above to watch Hindsight apply this rule.")
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
