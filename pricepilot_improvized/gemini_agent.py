import time
import base64
import urllib.parse
from datetime import datetime
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
    "Reliance Digital": "https://www.reliancedigital.in/products?q={{q}}",
    "Amazon": "https://www.amazon.in/s?k={{q}}",
    "Flipkart": "https://www.flipkart.com/search?q={q}",
    "Croma": "https://www.croma.com/searchB?q={{q}}%3Arelevance",
}

# -----------------------------
# SCRAPER API HTML FETCH
# -----------------------------
def get_page_html(url):
    payload = {
        "api_key": st.secrets["SCRAPER_API_KEY"],
        "url": url,
        "render": "true",
        "premium": "true",
        "country_code": "in"
    }

    response = requests.get(
        "http://api.scraperapi.com/",
        params=payload,
        timeout=60
    )

    return response.text


# -----------------------------
# SERPER SHOPPING API
# -----------------------------
def get_popular_sites(product, state):

    headers = {
        "X-API-KEY": st.secrets["SERPER_API_KEY"],
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

    for item in data.get("shopping", [])[:5]:

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
# PRICE COMPARISON
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

            log(state, f"🌐 Opening {site}", "info")

            html = get_page_html(product_url)
            state["current_html"] = html

            serper_price = data.get("price", "")

            match = re.search(r"\d[\d,]*", str(serper_price))

            if not match:
                log(state, f"{site}: invalid price", "warning")
                continue

            price = float(match.group().replace(",", ""))

            results[site] = {
                "price": price,
                "product_url": product_url
            }

            log(state, f"✅ {site}: ₹{price}", "success")

        except Exception as e:
            log(state, f"{site} failed: {e}", "warning")

    if not results:
        return None

    sorted_sites = sorted(results.items(), key=lambda x: x[1]["price"])
    top2 = sorted_sites[:2]

    state["top2_sites"] = {site: data for site, data in top2}

    state["selected_sites"] = {}

    for site, data in state["top2_sites"].items():
        state["selected_sites"][site] = {
            "price": data["price"],
            "product_url": data["product_url"],
            "offers": {}
        }

    log(state, f"🏆 Top 2: {', '.join(state['top2_sites'].keys())}", "success")

    return True


# -----------------------------
# HELPERS
# -----------------------------
def extract_number(text):
    try:
        match = re.search(r"\d[\d,\.]*", str(text))
        return float(match.group().replace(",", "")) if match else None
    except:
        return None


def is_valid_discount(txt):
    value = extract_number(txt)
    return value is not None and value > 0


def is_realistic_price(final_price, base_price):
    val = extract_number(final_price)
    return val is not None and 0 < val <= base_price


# -----------------------------
# GEMINI OFFER EXTRACTION (UNCHANGED LOGIC)
# -----------------------------
def extract_offers_from_html(html, state, base_price):

    log(state, "🌐 Extracting offers from page HTML...", "info")

    keywords = ["offer", "bank", "discount", "more"]

    for word in keywords:
        try:
            if word in html.lower():
                break
        except:
            continue

    text = re.sub(r"<script.*?>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style.*?>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)

    PROMPT = f"""
    Extract ONLY real offers from this product page text.

    Look inside:
    - visible text
    - hidden HTML
    - JSON scripts
    - structured data (JSON-LD)

    Return every possible:
    - bank offer
    - coupon
    - exchange offer
    - cashback
    - EMI discount

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

        return json.loads(res.text)

    except Exception as e:
        log(state, f"⚠️ Offer extraction failed: {e}", "warning")
        return None


# -----------------------------
# APPLY OFFERS
# -----------------------------
def apply_coupons(page, state):

    base_price = state.get("current_price", 0)
    html = state.get("current_html", "")

    data = extract_offers_from_html(html, state, base_price)

    if not data:
        log(state, "ℹ️ No offers found", "info")
        data = {"bank_offers": [], "coupons": [], "exchange_offers": []}

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


# -----------------------------
# INSIGHT GENERATION
# -----------------------------
def generate_insight(state):

    sites = state.get("selected_sites", {})

    if len(sites) < 2:
        return

    prompt = f"""
    Compare deals:

    {json.dumps(sites, indent=2)}

    Give:
    - Best deal reasoning
    - Product insight
    """

    res = client.models.generate_content(
        model="models/gemini-2.5-flash-lite",
        contents=prompt
    )

    state["insight"] = res.text.strip()


# -----------------------------
# MAIN RUN (NO PLAYWRIGHT)
# -----------------------------
def run(product, goal, state):

    state["agent_running"] = True
    state["product"] = product

    try:
        success = compare_prices(product, None, state)

        if not success:
            log(state, "No results", "error")
            return

        for site, data in state["top2_sites"].items():

            url = data["product_url"]

            log(state, f"🌐 Processing {site}", "info")

            html = get_page_html(url)

            state["current_html"] = html
            state["current_price"] = data["price"]

            apply_coupons(None, state)

            state["selected_sites"][site]["offers"] = state["offers"]

        generate_insight(state)

    except Exception as e:
        log(state, f"Error: {e}", "error")

    finally:
        state["agent_running"] = False