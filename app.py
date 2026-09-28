import os

import streamlit as st
from dotenv import load_dotenv

import agent
import memory
import seed_data
from prompts import DEMO_PROMPTS

load_dotenv()
st.set_page_config(page_title="Shyft Swap Mediator", page_icon="🗓️", layout="wide")

for key, default in [("last", None), ("seeded", False), ("saved", 0), ("error", None), ("saved_dispute", None)]:
    st.session_state.setdefault(key, default)

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
    st.header("Memories recalled")
    memory_panel = st.container()

# ---------------- main ----------------
st.title("🗓️ Shyft Swap Mediator")
st.caption("Brewline Café · Priya Nair, shift manager · memory by Hindsight")

st.write("**Demo disputes**")
cols = st.columns(len(DEMO_PROMPTS))
pending = None
for col, (label, text) in zip(cols, DEMO_PROMPTS.items()):
    if col.button(label, use_container_width=True):
        pending = text

typed = st.chat_input("Describe a shift-swap dispute...")
message = pending or typed

if message:
    st.session_state.error = None
    try:
        with st.spinner("Thinking..."):
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

    if compare and last.get("off") is not None:
        left, right = st.columns(2)
        with left:
            st.subheader("Without memory")
            st.write(last["off"]["answer"])
            if last["off"].get("model"):
                st.caption(f"Model: {last['off']['model']}")
            if last["off"].get("from_cache"):
                st.caption("Served from cached demo run (live model rate-limited)")
        with right:
            if last["on"].get("memory_error"):
                st.warning("Memory unavailable: answer below is NOT using Hindsight")
            st.subheader("With Hindsight memory")
            st.write(last["on"]["answer"])
            if last["on"].get("model"):
                st.caption(f"Model: {last['on']['model']}")
            if last["on"].get("from_cache"):
                st.caption("Served from cached demo run (live model rate-limited)")
    else:
        if last["on"].get("memory_error"):
            st.warning("Memory unavailable: answer below is NOT using Hindsight")
        st.subheader("With Hindsight memory")
        st.write(last["on"]["answer"])
        if last["on"].get("model"):
            st.caption(f"Model: {last['on']['model']}")
        if last["on"].get("from_cache"):
            st.caption("Served from cached demo run (live model rate-limited)")

    st.divider()
    st.write("**Priya's final ruling** (saved to memory so future disputes stay consistent)")
    ruling = st.text_area("Edit or paste the ruling", value=last["on"]["answer"], height=140,
                          key=f"ruling_{hash(last['message'])}")
    
    is_blank = not ruling or not ruling.strip()
    already_saved = (st.session_state.saved_dispute == last["message"])
    save_disabled = already_saved or is_blank

    if is_blank:
        st.caption("Enter a non-empty ruling to save.")
    elif already_saved:
        st.caption("✓ Ruling saved to memory for this dispute.")

    if st.button("Save ruling to memory", disabled=save_disabled):
        if is_blank:
            st.error("Cannot save an empty ruling.")
        else:
            try:
                agent.record_ruling(last["message"], ruling.strip())
                st.session_state.saved += 1
                st.session_state.saved_dispute = last["message"]
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
