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
        "selected_sites": {}  # 🔥 NEW
    }

if "agent_thread" not in st.session_state:
    st.session_state.agent_thread = None

# -------------------------------
# PAGE CONFIG
# -------------------------------
st.set_page_config(page_title="PricePilot", layout="wide")
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
    st.session_state.agent_state["selected_sites"] = {}

    extra_codes = []

    thread = threading.Thread(
        target=agent.run,
        args=(product, "", st.session_state.agent_state, extra_codes),
        daemon=True,
    )
    thread.start()
    st.session_state.agent_thread = thread

def stop_agent():
    st.session_state.agent_state["agent_running"] = False

# -------------------------------
# NAVBAR
# -------------------------------
current_product = st.session_state.agent_state.get('current_product', '').strip()

st.markdown(
    f"""
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">

    <style>
    .navbar {{
        position: sticky;
        top: 0;
        background: linear-gradient(90deg, #4B6CFE, #667EFF);
        color: white;
        padding: 15px 20px;
        font-size: 26px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-radius: 10px;
        margin-bottom: 15px;
    }}
    .product {{
        font-size: 14px;
        color: #a0ffff;
        font-weight: normal;
        max-width: 50%;
        text-align: right;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}
    </style>

    <div class="navbar">
        <div><i class="fas fa-tag"></i> PricePilot</div>
        <div class="product">{current_product if current_product else ""}</div>
    </div>

     
    """,
    unsafe_allow_html=True,
)


# -------------------------------
# LAYOUT
# -------------------------------
left, right = st.columns([1, 1])

# -------------------------------
# LEFT PANEL
# -------------------------------
with left:
    st.subheader("🛒 Product Search")

    product = st.text_input(
        "Enter the product you want to track",
        placeholder="e.g., Redmi 15C 5G 128 GB, 6 GB RAM, Mobile Phone",
        help="Include brand, model, and variant for better accuracy"
    )

    st.markdown(
        "<div style='font-size:13px; color:gray;'>💡 Tip: Be as specific as possible. Include brand, model, storage, or variant.</div>",
        unsafe_allow_html=True
    )

    st.markdown("<br>", unsafe_allow_html=True)
    
    st.session_state.agent_state["current_product"] = product

    col1, col2 = st.columns(2)
    with col1:
        st.button("🟢 Start Search Assistant", on_click=start_agent, use_container_width=True)

    with col2:
        st.button("⛔ Stop Search Assistant", on_click=stop_agent, use_container_width=True)
    
    state = st.session_state.agent_state

    # ---------------------------
    # 🔥 NEW: SIDE-BY-SIDE DEALS
    # ---------------------------
    sites_data = state.get("selected_sites", {})

    if sites_data:
        st.markdown("## Compare Deals")

        selected_site = st.radio(
            "Choose website",
            list(sites_data.keys()),
            horizontal=True
        )

        cols = st.columns(len(sites_data))

        for i, (site, data) in enumerate(sites_data.items()):
            with cols[i]:
                st.markdown(f"### 🛍️ {site}")

                base_price = data["price"]
                st.markdown(f"💰 **Base Price:** ₹{base_price:,.0f}")

                offers = data.get("offers", {})

                all_offers = (
                    offers.get("bank_offers", []) +
                    offers.get("coupons", []) +
                    offers.get("exchange_offers", [])
                )

                if all_offers:
                    st.markdown("#### 🎁 Offers")

                    all_offers = sorted(
                        all_offers,
                        key=lambda x: to_number(x.get("final_price", base_price))
                    )

                    for offer in all_offers:
                        discount = offer.get("discount", "")
                        final_price = to_number(offer.get("final_price", base_price))

                        if "bank" in offer:
                            label = f"🏦 {offer.get('bank')}"
                        elif "code" in offer:
                            label = f"🏷️ {offer.get('code')}"
                        else:
                            label = "🔁 Exchange"

                        st.markdown(
                            f"""
                            <div style="
                                background-color:#f8f9fa;
                                padding:10px;
                                border-radius:10px;
                                margin-bottom:8px;
                            ">
                                <b>{label}</b><br>
                                Save ₹{discount}<br>
                                <span style="color:green; font-weight:bold;">
                                    Final: ₹{final_price:,.0f}
                                </span>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                else:
                    st.info("No offers available")

                if site == selected_site:
                    st.markdown(
                        "<div style='color:green; font-weight:bold;'>✅ Selected</div>",
                        unsafe_allow_html=True
                    )

        # ---------------------------
        # 🛒 BUY BUTTON
        # ---------------------------
        selected_data = sites_data.get(selected_site, {})
        buy_url = selected_data.get("product_url") or selected_data.get("search_url")

        st.markdown("---")
        
        if buy_url:
            st.markdown(f"""
                        
            <!-- Load Font Awesome -->
            <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">

            <style>
            .buy-button {{
                background: linear-gradient(90deg, #4B6CFE, #667EFF);
                color: white !important;
                padding: 10px 25px;
                border-radius: 10px;
                font-size: 16px;
                font-weight: 600;
                text-decoration: none; /* This removes the underline */
                display: inline-block;
                transition: 0.2s all ease;
            }}
            .buy-button, 
            .buy-button:link, 
            .buy-button:visited, 
            .buy-button:hover, 
            .buy-button:active, 
            .buy-button:focus {{
                text-decoration: none !important;
                color: white !important;
            }}
            .buy-button:hover {{
                opacity: 0.85;
                transform: translateY(-1px);
            }}
            </style>

            <a class="buy-button" href="{buy_url}" target="_blank">
                <i class="fas fa-cart-shopping"></i> Buy from {selected_site}
            </a>
            """, unsafe_allow_html=True)
        else:
            st.warning("No product link available")

# -------------------------------
# RIGHT PANEL
# -------------------------------
with right:
    if state.get("agent_running"):
        st.subheader("Assistant Progress")
        progress = min(len(state["action_log"]), 10) * 10
        st.progress(progress)

    st.subheader("📜 Live Logs")

    
    # 🔥 Force re-render when insight arrives
    expander_key = "logs_open" if not state.get("insight") else "logs_closed"
    with st.expander("Logs", expanded=not state.get("insight"), key=expander_key):
       
    
        for log in state["action_log"]:
            msg = log.get("msg", "")
            typ = log.get("type", "info")
            
            # Map type to color
            color = {
                "info": "#0077CC",      # Darker Blue
                "success": "#228B22",   # Forest Green
                "warning": "#FF8C00",   # Dark Orange
                "error": "#B22222"      # Firebrick Red
            }.get(typ, "#000000")       # default black
            # Render inline like a terminal
            st.markdown(
                f'<span style="color:{color}; font-family:monospace;">[12:34:56] {typ.upper():7} {msg}</span><br>', 
                unsafe_allow_html=True
            )
        
        st.markdown('</div>', unsafe_allow_html=True)
    # ---------------------------
    # 🧠 AI INSIGHT
    # ---------------------------
    if state.get("insight"):
        st.markdown("## 🧠 Smart Recommendation")

        st.markdown(
            f"""
            <div style="
                background-color:#eef4ff;
                padding:15px;
                border-radius:12px;
                border-left:5px solid #4B6CFE;
                font-size:16px;
            ">
                {state['insight']}
            </div>
            """,
            unsafe_allow_html=True
        )

# -------------------------------
# AUTO REFRESH
# -------------------------------
if state.get("agent_running"):
    time.sleep(1)
    st.rerun()


