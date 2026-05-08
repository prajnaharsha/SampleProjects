import time
import base64
import urllib.parse
from datetime import datetime
from playwright.sync_api import sync_playwright
from google import genai
import requests
import streamlit as st
import re
import json 
from urllib.parse import urljoin
from bs4 import BeautifulSoup
# -----------------------------
# INIT
# -----------------------------
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
FALLBACK_SITES = {
   #"SapnaOnline": "https://www.sapnaonline.com/search?keyword={{q}}",
   #"Bookswagon": "https://www.bookswagon.com/search-books/{{q}}",
   #"Myntra":   "https://www.myntra.com/{{q}}",
   #"Ajio":     "https://www.ajio.com/search/?text={{q}}",   
   "Reliance Digital": "https://www.reliancedigital.in/products?q={{q}}",    
   "Amazon": "https://www.amazon.in/s?k={{q}}",
   "Flipkart": "https://www.flipkart.com/search?q={q}"   ,
   "Croma": "https://www.croma.com/searchB?q={{q}}%3Arelevance",
   #"Shopclues": "https://www.shopclues.com/search?q={{q}}",   
}

def get_page_html(url):

    payload = {
        "api_key": st.secrets["SCRAPER_API_KEY"],
        "url": url,
        "render": "true"
    }

    response = requests.get(
        "http://api.scraperapi.com/",
        params=payload,
        timeout=60
    )

    return response.text


def get_popular_sites(product, state):

    headers = {
        "X-API-KEY": st.secrets["SERPER_API_KEY"] ,
        "Content-Type": "application/json"
    }

    payload = {
        "q": product,
        "gl": "in",
        "hl": "en"
    }

    response = requests.post(
        "https://google.serper.dev/shopping",
        json=payload,
        headers=headers
    )

    data = response.json()

    results = {}

    shopping_results = data.get("shopping", [])[:10]

    for item in shopping_results:

        source = item.get("source", "")
        link = item.get("link", "")
        price = item.get("price", "")

        if not source or not link:
            continue

        results[source] = {
            "product_url": link,
            "price": price
        }

    return results
    
# -----------------------------
# LOGGER
# -----------------------------
def log(state, msg, type="info"):
    ts = datetime.now().strftime("%H:%M:%S")
    state["action_log"].append({
        "msg": f"[{ts}] {msg}",
        "type": type
    })




# -----------------------------
# STEP 1: COMPARE PRICES
# -----------------------------
def compare_prices(product, page, state):

    compare_sites = get_popular_sites(product, state)

    if not compare_sites:
        log(state, "❌ No shopping results found", "error")
        return None

    results = {}

    for site, data in compare_sites.items():

        try:
            product_url = data.get("product_url")

            if not product_url:
                continue

            log(state, f"🌐 Opening {site}", "info")

            page.goto(product_url, timeout=20000)

            page.wait_for_timeout(2500)
         
            serper_price = data.get("price", "")

            match = re.search(r"\d[\d,]*", str(serper_price))

            if not match:
                log(state, f"{site}: invalid price", "warning")
                continue

            price = float(
                match.group().replace(",", "")
            )

            # AI fallback
          

            results[site] = {
                "price": price,
                "product_url": product_url
            }

            log(state, f"✅ {site}: ₹{price}", "success")

        except Exception as e:
           log(state, f"{site} failed: {e}", "warning")

    if not results:
        return None

    # sort cheapest first
    sorted_sites = sorted(
        results.items(),
        key=lambda x: x[1]["price"]
    )

    top2 = sorted_sites[:2]

    state["top2_sites"] = {
        site: data for site, data in top2
    }

    state["selected_sites"] = {}

    for site, data in state["top2_sites"].items():

        state["selected_sites"][site] = {
            "price": data["price"],
            "product_url": data["product_url"],
            "offers": {}
        }

    log(
        state,
        f"🏆 Top 2: {', '.join(state['top2_sites'].keys())}",
        "success"
    )

    return True

# -----------------------------
# NAVIGATE
# -----------------------------
def navigate(page, url, state, site):
    try:
        page.goto(url)
        log(state, f"🌐 Navigated to {site}")
    except Exception as e:
        log(state, f"Navigation failed: {e}", "error")   


def extract_number(text):
    try:
        match = re.search(r"\d[\d,\.]*", str(text))
        if not match:
            return None
        return float(match.group().replace(",", ""))
    except:
        return None


def is_valid_discount(txt):
    value = extract_number(txt)
    return value is not None and value > 0



def extract_json(text):
    import json

    try:
        # Remove markdown wrappers
        text = text.replace("```json", "").replace("```", "").strip()

        # Extract ONLY valid JSON block
        start = text.find("{")
        end = text.rfind("}")

        if start != -1 and end != -1:
            json_str = text[start:end+1]
            return json.loads(json_str)

    except Exception as e:
        print("JSON parse error:", e)

    return {
        "bank_offers": [],
        "coupons": [],
        "exchange_offers": []
    }

def extract_offers_from_html(page, state,base_price):
   
    log(state, "🌐 Extracting offers from page HTML...", "info")

    # Step 1: Try expanding offer sections
    keywords = ["offer", "bank", "discount", "more"]

    for word in keywords:
        try:
            el = page.locator(f"text={word}").first
            if el.count() > 0 and el.is_visible():
                el.click()
                page.wait_for_timeout(1500)
                log(state, f"🔍 Clicked '{word}' to reveal offers", "info")
                break
        except:
            continue

    # Step 2: Get HTML
    html = page.content()

    # Step 3: Clean HTML → text
    text = re.sub(r"<script.*?>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style.*?>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)

    #text = text[:8000]  # limit size

    # Step 4: AI extraction
    PROMPT = f"""
    Extract ONLY real offers from this product page text.

    {text}

    Base product price: ₹{base_price}

    Rules:
    - DO NOT guess
    - Only extract clearly visible offers
    - Ignore EMI / financing

    FINAL PRICE CALCULATION RULES:
    1. Fixed discount:
    - Example: "₹2000 off"
    - discount_value = 2000

    2. Percentage discount only:
    - Example: "10% off"
    - discount_value = (10/100) * base_price

    3. "Up to ₹X" (no % mentioned):
    - Example: "Up to ₹1200 off"
    - discount_value = X (use as maximum possible discount)

    4. "X% up to ₹Y":
    - Example: "7.5% up to ₹7500"
    - Calculate X% of base_price
    - discount_value = MIN(calculated_value, Y)

    FINAL PRICE:
    - final_price = base_price - discount_value
    - Do not inject discount_value into the discount text; discount text must be exactly as on the page

    IMPORTANT:
    - You MUST calculate final_price for every offer
    - If exact discount is unclear, skip it (do NOT guess numbers)
    - Only use discount_value for numeric calculation

    Return JSON:
    {{
    "bank_offers": [
        {{"bank": "", "discount": "", "final_price": ""}}
    ],
    "coupons": [
        {{"code": "", "discount": "", "final_price": ""}}
    ],
    "exchange_offers": [
        {{"discount": "", "final_price": ""}}
    ]
    }}
    """

    try:
        res = client.models.generate_content(
            model="models/gemini-2.5-flash-lite",
            contents=PROMPT,
            config={"response_mime_type": "application/json"}
        )
        
        data = json.loads(res.text)

        #log(state, f"✅ RAW AI Response: {res.text}", "success")        

        return data

    except Exception as e:
        if "429" in str(e):
            log(state, "⚠️ HTML extraction failed: AI limit reached", "warning")
        else:
            log(state, "⚠️ HTML extraction failed: Could not fetch data from AI", "warning")
        return None
    
def apply_coupons(page, state):

    base_price = state.get("current_price", 0)
  
    # -----------------------------
    # 🥇 STEP 1: Try HTML extraction
    # -----------------------------
    data = extract_offers_from_html(page, state,base_price)

    # Check if valid offers found
    def has_offers(d):
        if not d:
            return False
        return any([
            d.get("bank_offers"),
            d.get("coupons"),
            d.get("exchange_offers")
        ])

    # -----------------------------
    # NO  OFFERS
    # -----------------------------
    if not has_offers(data):
        log(state, "ℹ️ No offers found on page", "info")
        data = {
            "bank_offers": [],
            "coupons": [],
            "exchange_offers": []
        }  
        
    #log(state, f"🧪 Raw AI offers: {json.dumps(data)}", "info")
   
    
    state["offers"] = {
        "bank_offers": [
            b for b in data.get("bank_offers", [])
            if is_valid_discount(b.get("discount"))
            and is_realistic_price(b.get("final_price"), base_price)
        ],
        "coupons": [
            c for c in data.get("coupons", [])
            if is_valid_discount(c.get("discount"))
            and is_realistic_price(c.get("final_price"), base_price)
        ],
        "exchange_offers": [
            e for e in data.get("exchange_offers", [])
            if is_valid_discount(e.get("discount"))
            and is_realistic_price(e.get("final_price"), base_price)
        ]
    }

    log(state, "🎯 Final offers ready", "success")
    #log(state, f"📦 Final offers: {json.dumps(state['offers'], indent=2)}", "info")


def is_realistic_price(final_price, base_price):
    val = extract_number(final_price)
    if val is None:
        return False
    return 0 < val <= base_price


def generate_insight(state):
    try:
        sites = state.get("selected_sites", {})

        if not sites or len(sites) < 2:
            return

        summary = {
            "product": state.get("product"),
            "sites": {}
        }

        for site, data in sites.items():
            summary["sites"][site] = {
                "base_price": data.get("price"),
                "offers": data.get("offers", {})
            }

        PROMPT = f"""
        You are a smart shopping assistant.

        Compare these 2 deals AND give product insight.

        Data:
        {json.dumps(summary, indent=2)}

        Instructions:
        1. Deal Insight:
        - Which site is better and why
        - Consider final price, reliability, realism of offers
        - 

        2. Product Insight:
        - Is this product generally good?
        - Any known pros/cons
        - Who should buy it

        Rules:
        - Max 6-7 lines total
        - Be crisp and practical
        - Add a blank line after Deal Insight section
        - No fluff

        Output format:

        **Deal Insight:**
        ...

        **Product Insight:**
        ...
        """

        res = client.models.generate_content(
            model="models/gemini-2.5-flash-lite",
            contents=PROMPT
        )

        state["insight"] = res.text.strip()

        log(state, "🧠 Insight generated", "success")

    except Exception as e:
        if "429" in str(e):
            log(state, "⚠️ Insight failed: AI limit reached", "warning")
        else:
            log(state, "⚠️ Insight failed: Could not fetch data from AI", "warning")

# -----------------------------
# MAIN RUN
# -----------------------------
def run(product, goal, state):

    with sync_playwright() as p:

        browser = p.chromium.launch_persistent_context(
            user_data_dir="user_data",
            headless=False
        )
        page = browser.new_page()

        state["agent_running"] = True
        state["product"] = product

        try:
            success = compare_prices(product, page, state)

            if not success:
                log(state, "No prices found", "error")
                return

            # 🔥 NEW: process BOTH sites
            for site, data in state["top2_sites"].items():

                url = data.get("product_url") or data.get("search_url")

                log(state, f"🌐 Processing {site}", "info")

                navigate(page, url, state, site)

                # reuse existing logic
                state["current_price"] = data["price"]
                state["best_site"] = site

                apply_coupons(page, state)

                # store offers per site
                state["selected_sites"][site]["offers"] = state["offers"]
           

        except Exception as e:
            log(state, f"Error: {e}", "error")

        try:
            generate_insight(state)
        except Exception:
            log(state, "⚠️ Insight unavailable (quota reached)", "warning")
        finally:
            state["agent_running"] = False