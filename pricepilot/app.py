import asyncio, sys

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import streamlit as st
import threading
import time
import gemini_agent as agent  # always use Gemini
import re

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
    }

if "agent_thread" not in st.session_state:
    st.session_state.agent_thread = None

# -------------------------------  
# PAGE CONFIG  
# -------------------------------  
st.set_page_config(page_title="PricePilot", layout="wide")

st.title("🛒 PricePilot – AI Deal Finder")

# -------------------------------  
# LAYOUT (MAIN CHANGE)  
# -------------------------------  
left, right = st.columns([1, 1])

# ===============================
# LEFT SIDE (MAIN UI)
# ===============================
with left:
    st.subheader("🔍 Search")

    product = st.text_input("Enter product", "Samsung Galaxy S21 FE")
    goal = st.text_input("Goal", "Find cheapest price and apply best coupon")
    user_codes = st.text_input("Extra coupon codes (comma separated)", "")

    # ---------------------------
    # START / STOP
    # ---------------------------
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

    def to_number(price):
        if isinstance(price, (int, float)):
            return price
        if isinstance(price, str):
            cleaned = re.sub(r"[^\d.]", "", price)
            return float(cleaned) if cleaned else 0
        return 0

    def stop_agent():
        st.session_state.agent_state["agent_running"] = False

    col1, col2 = st.columns(2)
    with col1:
        st.button("▶ Start Agent", on_click=start_agent)
    with col2:
        st.button("⛔ Stop Agent", on_click=stop_agent)

    state = st.session_state.agent_state

    # ---------------------------
    # FINAL RESULTS (NEW)
    # ---------------------------
    st.subheader("💰 Results")

    if state.get("price_comparison"):
        st.write("**Price Comparison:**")
        for site, data in state["price_comparison"].items():
            st.write(f"- {site}: ₹{data['price']:,.0f}")

    if state.get("original_price"):
        st.write(f"Original Price: ₹{state['original_price']:,.0f}")

    if state.get("current_price"):
        st.write(f"Final Price: ₹{state['current_price']:,.0f}")

    offers = state.get("offers", {})

    all_offers = (
        offers.get("bank_offers", []) +
        offers.get("coupons", []) +
        offers.get("exchange_offers", [])
    )

    if all_offers:
        st.subheader("🎁 Available Offers")

        label_to_offer = {}

        options = []

        # ✅ NONE (top, visually separated)
        options.append("🚫 None")

        # BANK OFFERS
        bank_offers = offers.get("bank_offers", [])
   
        for o in bank_offers:
            label = f"🏦 {o.get('bank', 'Bank')} - {o.get('discount', '')}"
            options.append(label)
            label_to_offer[label] = o

        # COUPONS
        coupons = offers.get("coupons", [])
        for o in coupons:
            label = f"🏷️ Code {o.get('code', '')} - {o.get('discount', '')}"
            options.append(label)
            label_to_offer[label] = o

        # EXCHANGE
        exchange_offers = offers.get("exchange_offers", [])
        for o in exchange_offers:
            label = f"🔄 {o.get('discount', '')}"
            label = f"🏷️ Exchange Offer - {o.get('discount', '')}"
            options.append(label)
            label_to_offer[label] = o

        # 🔘 SINGLE radio (enforces one selection)
        selected = st.radio(
            "Select an offer (only one can be selected)",
            options,
            index=0
        )

        # 💰 Logic
        if selected != "🚫 None":
            chosen_offer = label_to_offer[selected]
            final_price = to_number(chosen_offer.get("final_price", state['current_price']))
            st.markdown(f"### 💰 Final Price: ₹{final_price:,.0f}", unsafe_allow_html=True)
        else:
            price = to_number(state['current_price'])
            st.markdown(f"### 💰 Final Price: ₹{price:,.0f}", unsafe_allow_html=True)
    
    #if state.get("best_code"):
    #    st.success(f"Best Coupon Applied: {state['best_code']}")

        

# ===============================
# RIGHT SIDE (LOGS)
# ===============================
with right:
    st.subheader("📜 Live Logs")
    log_container = st.container(height=500)

    with log_container:
        for log in st.session_state.agent_state["action_log"]:
            msg = log.get("msg", "")
            typ = log.get("type", "info")

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
if st.session_state.agent_state.get("agent_running"):
    time.sleep(1)
    st.rerun()