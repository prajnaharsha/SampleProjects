import asyncio, sys
import threading
import time
import re
import streamlit as st
import gemini_agent as agent  # always use Gemini

# -------------------------------
# Windows asyncio fix
# -------------------------------
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# -------------------------------
# INIT STATE
# -------------------------------
if "agent_state" not in st.session_state:
    st.session_state.agent_state = {
        "action_log": [],
        "agent_running": False,
        "approval_pending": False,
        "approval_action": None,
        "approval_response": None,
        "approval_saving": 0,
        "best_code": None,
        "original_price": None,
        "current_price": None,
        "price_comparison": {},
        "offers": {},
        "current_product": "",
    }

if "agent_thread" not in st.session_state:
    st.session_state.agent_thread = None

# -------------------------------
# PAGE CONFIG
# -------------------------------
st.set_page_config(page_title="PricePilot", layout="wide")

# -------------------------------
# HELPER FUNCTIONS
# -------------------------------
def to_number(price):
    if isinstance(price, (int, float)):
        return price
    if isinstance(price, str):
        cleaned = re.sub(r"[^\d.]", "", price)
        return float(cleaned) if cleaned else 0
    return 0

def start_agent():
    if st.session_state.agent_state["agent_running"]:
        return
    st.session_state.agent_state["action_log"] = []
    st.session_state.agent_state["agent_running"] = True
    st.session_state.agent_state["approval_pending"] = False
    st.session_state.agent_state["approval_response"] = None
    st.session_state.agent_state["best_code"] = None

    extra_codes = []
    if user_codes.strip():
        extra_codes = [c.strip() for c in user_codes.split(",") if c.strip()]

    thread = threading.Thread(
        target=agent.run,
        args=(
            product,
            goal,
            st.session_state.agent_state,
            extra_codes,
        ),
        daemon=True,
    )
    thread.start()
    st.session_state.agent_thread = thread

def stop_agent():
    st.session_state.agent_state["agent_running"] = False

# -------------------------------
# NAVBAR (Sticky Top, no rounded corners)
# -------------------------------
current_product = st.session_state.agent_state.get('current_product', '').strip()

st.markdown(
    f"""
    <style>
    .navbar {{
        position: sticky;
        top: 0;
        background-color: #4B6CFE;
        color: white;
        padding: 15px;
        font-size: 24px;
        text-align: center;
        z-index: 9999;
    }}
    .fancy-button {{
        background-color:#4B6CFE;
        color:white;
        padding:10px 20px;
        border-radius:8px;
        border:none;
        cursor:pointer;
        font-size:16px;
        margin-right:10px;
    }}
    .fancy-button.stop {{
        background-color:#FF4B4B;
    }}
    .fancy-button:hover {{
        opacity:0.8;
    }}
    </style>
    <div class="navbar">
        🛒 PricePilot{f' – {current_product}' if current_product else ''}
    </div>
    """,
    unsafe_allow_html=True,
)

# ===============================
# SEARCH & LAYOUT
# ===============================
left, right = st.columns([1, 1])

with left:
    st.subheader("🔍 Search")
    product = st.text_input("Enter product", "Samsung Galaxy S21 FE")
    goal = ""  # Keep empty string for backward compatibility
    user_codes = ""  # Keep empty string for backward compatibility

    st.session_state.agent_state["current_product"] = product

    # Only colored Start/Stop buttons
 

    # Hidden Streamlit buttons for callback
    col1, col2 = st.columns(2)
    with col1:
        st.button("▶ Start Agent", on_click=start_agent)
    with col2:
        st.button("⛔ Stop Agent", on_click=stop_agent)

    state = st.session_state.agent_state

    # ---------------------------
    # PRICE COMPARISON
    # ---------------------------
    if state.get("price_comparison"):
        st.markdown("### 🏷️ Price Comparison")
        for site, data in state["price_comparison"].items():
            st.metric(label=site, value=f"₹{data['price']:,.0f}")

    # ---------------------------
    # PRICE OVERVIEW
    # ---------------------------
    if state.get("original_price") and state.get("current_price"):
        st.markdown("### 💸 Price Overview")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Original Price", f"₹{state['original_price']:,.0f}", delta_color="off")
        with col2:
            st.metric("Current Price", f"₹{state['current_price']:,.0f}", delta_color="normal")

    # ---------------------------
    # OFFERS - COLORFUL CARDS
    # ---------------------------
    offers = state.get("offers", {})
    all_offers = offers.get("bank_offers", []) + offers.get("coupons", []) + offers.get("exchange_offers", [])

    if all_offers:
        st.markdown("### 🎁 Available Offers")
        label_to_offer = {}
        options = ["🚫 None"]

        for o in offers.get("bank_offers", []):
            label = f"🏦 {o.get('bank')} - {o.get('discount', '')}"
            options.append(label)
            label_to_offer[label] = o
            st.markdown(
                f"<div style='border-radius:10px;padding:10px;margin:5px;background-color:#d4edda'>"
                f"<b>🏦 Bank Offer</b><br>{o.get('bank')} - {o.get('discount', '')}</div>",
                unsafe_allow_html=True,
            )

        for o in offers.get("coupons", []):
            label = f"🏷️ Code {o.get('code')} - {o.get('discount', '')}"
            options.append(label)
            label_to_offer[label] = o
            st.markdown(
                f"<div style='border-radius:10px;padding:10px;margin:5px;background-color:#d1ecf1'>"
                f"<b>🏷️ Coupon</b><br>Code: {o.get('code')} - {o.get('discount', '')}</div>",
                unsafe_allow_html=True,
            )

        for o in offers.get("exchange_offers", []):
            label = f"🔄 Exchange - {o.get('discount', '')}"
            options.append(label)
            label_to_offer[label] = o
            st.markdown(
                f"<div style='border-radius:10px;padding:10px;margin:5px;background-color:#fff3cd'>"
                f"<b>🔄 Exchange</b><br>{o.get('discount', '')}</div>",
                unsafe_allow_html=True,
            )

        selected = st.radio("Select an offer", options, index=0)

        if selected != "🚫 None":
            chosen_offer = label_to_offer[selected]
            final_price = to_number(chosen_offer.get("final_price", state['current_price']))
            st.markdown(f"<h3 style='color:green'>💰 Final Price After Offer: ₹{final_price:,.0f}</h3>", unsafe_allow_html=True)
        else:
            st.markdown(f"<h3 style='color:blue'>💰 Final Price: ₹{state['current_price']:,.0f}</h3>", unsafe_allow_html=True)

# ===============================
# RIGHT SIDE - PROGRESS + LIVE LOGS
# ===============================
with right:
    if state.get("agent_running"):
        st.subheader("🤖 Agent Progress")
        progress = min(len(state["action_log"]), 10) * 10
        st.progress(progress)

    st.subheader("📜 Live Logs")
    with st.expander("Show/Hide Logs", expanded=True):
        for log in state["action_log"]:
            msg, typ = log.get("msg", ""), log.get("type", "info")
            if typ == "success":
                st.success(msg)
            elif typ == "warning":
                st.warning(msg)
            elif typ == "error":
                st.error(msg)
            else:
                st.info(msg)

# -------------------------------
# AUTO REFRESH
# -------------------------------
if state.get("agent_running"):
    time.sleep(1)
    st.rerun()