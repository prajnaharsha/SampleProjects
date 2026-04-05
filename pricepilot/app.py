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
# PAGE STYLING
# -------------------------------
st.markdown(
    """
    <style>
    /* Page background */
    .stApp {
        background-color: #f0f0f0;  /* light gray */
    }

    /* Make text input areas white */
    .stTextInput>div>div>input {
        background-color: white !important;
        color: black;
    }

    /* Optional: make text area white too */
    .stTextArea>div>div>textarea {
        background-color: white !important;
        color: black;
    }

    /* Optional: make selectbox white */
    .stSelectbox>div>div>div>select {
        background-color: white !important;
        color: black;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# -------------------------------
# HIDE STREAMLIT MENU / DEPLOY BUTTON
# -------------------------------
st.markdown(
    """
    <style>
    /* Hide top-right menu including Deploy button */
    #MainMenu {visibility: hidden !important;}

    /* Hide top header bar completely */
    header {visibility: hidden !important; height: 0px;}

    /* Hide footer (optional) */
    footer {visibility: hidden !important;}
    </style>
    """,
    unsafe_allow_html=True
)
st.markdown(
    """
    <style>
    /* Remove top padding from main app container */
    .css-18e3th9,  /* old Streamlit container */
    .block-container {
        padding-top: 0rem !important;
        margin-top: 0rem !important;
    }

    /* Remove margin from header wrapper */
    header, .stApp > header {
        display: none !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
    }

    /* Remove main menu space */
    #MainMenu {
        visibility: hidden !important;
        height: 0 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)
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

# Navbar with Font Awesome icons
st.markdown(
    f"""
    <!-- Load Font Awesome for icons -->
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">

    <style>
    /* Navbar Styling with fully rounded corners */
    .navbar {{
        position: sticky;
        top: 0;
        background: linear-gradient(90deg, #4B6CFE, #667EFF);
        color: white;
        padding: 18px 20px;
        font-size: 26px;
        font-weight: 600;
        text-align: center;
        z-index: 9999;
        border-radius: 25px; /* fully rounded */
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        margin: 10px; /* spacing from edges */
    }}
    .navbar i {{
        margin-right: 12px;
        color: #FFD700; /* Gold accent for the icon */
    }}
    </style>

    <div class="navbar">
        <i class="fas fa-tag"></i> PricePilot{f' – {current_product}' if current_product else ''}
    </div>
    """,
    unsafe_allow_html=True,
)

# -------------------------------
# LEFT PANEL - SEARCH & ACTIONS
# -------------------------------
left, right = st.columns([1,1])

with left:
    st.subheader("🔍 Search Product")

    # Product input with placeholder and notes
    product = st.text_input(
        "Enter the product you want to track",
        placeholder="e.g., Samsung Galaxy S21 FE, Apple iPhone 14 Pro",
        help="Include brand, model, and variant for better accuracy"
    )
    st.markdown(
        "<div class='input-note'>💡 Tip: Be as specific as possible. Include brand, model, storage, or variant.</div>",
        unsafe_allow_html=True
    )

    goal = ""  # optional, can add in future
    user_codes = ""  # optional coupon codes

    st.session_state.agent_state["current_product"] = product

    # Action buttons in a row
    col1, col2 = st.columns(2)
    with col1:
        st.button("🟢 Start Agent", on_click=start_agent, key="start_agent", 
                  help="Click to start tracking prices for this product")
    with col2:
        st.button("⛔ Stop Agent", on_click=stop_agent, key="stop_agent",
                  help="Click to stop the agent immediately")

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