import time
import base64
import urllib.parse
from datetime import datetime
from playwright.sync_api import sync_playwright
from google import genai
import streamlit as st
import re
import json 
from urllib.parse import urljoin
# -----------------------------
# INIT
# -----------------------------
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
FALLBACK_SITES = {
   "Myntra":   "https://www.myntra.com/{q}",
   "Ajio":     "https://www.ajio.com/search/?text={q}",
   "Reliance Digital": "https://www.reliancedigital.in/products?q={q}",    
   "Amazon":   "https://www.amazon.in/s?k={q}",
   "Flipkart": "https://www.flipkart.com/search?q={q}"   
}


DEFAULT_CODES = ["SAVE10", "SAVE20", "DEAL10"]

def get_popular_sites(product,state):
   
    """
    Ask AI to suggest top Indian e-commerce sites for a given product.
    Returns a dictionary {site_name: search_url_template}.
    """
    prompt = f"""
    Suggest 3 most popular Indian e-commerce websites for buying '{product}'.
    Give response as JSON in the format:
    {{
        "site_name": "search_url_with_placeholder_for_query"
    }}
    Example:
    {{
        "Amazon": "https://www.amazon.in/s?k={{q}}",
        "Flipkart": "https://www.flipkart.com/search?q={{q}}",
        "Reliance Digital": "https://www.reliancedigital.in/products?q={{q}}", 
        "Croma": "https://www.croma.com/searchB?q={{q}}%3Arelevance"
    }}

    Return ONLY these 4 websites with their exact search URLs:
    - Amazon
    - Flipkart
    - Reliance Digital
    - Croma

    Use the exact URL patterns given. Do not infer or modify them.

    """

    if "action_log" not in state:
        state["action_log"] = []

    try:
        res = client.models.generate_content(
            model="models/gemini-2.5-flash",
            contents=prompt  # just a string
        )
        #res = client.models.generate_content(
        #    model="gemini-2.0-flash",
        #    contents=prompt  # just a string
        #)
         
        raw_text = res.text.strip()        

        # Extract JSON object from text
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if match:
            sites_json = match.group()
            sites_dict = json.loads(sites_json)
            log(state, f"🔎 Parsed sites: {', '.join(sites_dict.keys())}", "info")
            return sites_dict
        else:
            raise ValueError("No JSON found in Gemini response")

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        log(state, f"⚠️ Failed to fetch popular sites dynamically: {e}\n{tb}", "warning")
        return {}  # return empty dict
    
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
# GEMINI (fallback only)
# -----------------------------
def ask_vision(image, prompt):
    b64 = base64.b64encode(image).decode()

    res = client.models.generate_content(
        model="models/gemini-2.5-flash",
        contents=[{
            "role": "user",
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/png", "data": b64}}
            ]
        }]
    )
    return res.text.strip()

# -----------------------------
# DOM PRICE EXTRACTION
# -----------------------------
def extract_price(page):
    # Wait for page to stabilize
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except:
        pass    
   

    selectors = [
        # Flipkart (product page)
         "div._30jeq3", 
        "div[class*='30jeq3']",
        "div[class*='price']",

        # Amazon
        "span.a-price-whole",
        "span.a-offscreen",

        # Reliance Digital (product cards)
        "div.product-wrapper div.price",
        "div.product-card div.price",
        "span.price",

        # Croma (product + listing pages)
        "span.amount",
        "span.new-price",
        "span.old-price",
        "div.price-section span",
        "div.product-price span",

        # Generic
        "span.price",
        ".product-price",
        "span[data-price]",
    ]

    for sel in selectors:
        try:
            el = page.locator(sel).first

            if el.count() == 0:
                continue

            raw = el.inner_text().strip()

            # 🔍 Extract only numbers safely
            match = re.search(r"\d[\d,]*", raw)

            if not match:
                continue

            price = float(match.group().replace(",", ""))

            if price > 0:
                return price

        except Exception:
            continue

    return None
# -----------------------------
# EXTRACT PRODUCT URL FROM DOM
# -----------------------------
def extract_product_url_from_dom(page, state, site):
    """
    Extract product URL from search results page using DOM selectors
    """
    try:
        # Site-specific selectors for product links
        site_selectors = {
            "Amazon": [
                "a[href*='/dp/']",
                "a.a-link-normal[href*='/dp/']",
                "div[data-component-type='s-search-result'] a[href*='/dp/']"
            ],
            "Flipkart": [
                "a[href*='/p/']",
                "a._1fQZEK",
                "div._1AtVbE a"
            ],
            "Myntra": [
                "a[href*='/p/']",
                ".product-base a"
            ],
            "Ajio": [
                "a[href*='/p/']",
                ".rilrtl-products-list a"
            ],
             "Reliance Digital": [
                 "a[href*='/product/']",       # matches any product link
                "div.product-wrapper a",      # product card wrapper
                "div.product-card a"          # alternate card layout
            ]
        }
        
        selectors = site_selectors.get(site, ["a[href*='/p/']", "a[href*='/dp/']"])
        
        for selector in selectors:
            try:
                links = page.locator(selector).all()
                
                for link in links[:3]:  # Check first 3 links
                    try:
                        href = link.get_attribute("href")
                        if href and not href.startswith(('javascript:', '#', 'void')):
                            # Make absolute URL if relative
                            href = urljoin(page.url, href)                            
                            #log(state, f"🔗 Found product URL for {site}", "success")
                            
                            return href
                    except:
                        continue
            except:
                continue
        
        log(state, f"⚠️ Could not find product URL for {site}", "warning")
        return None
        
    except Exception as e:
        log(state, f"Error extracting product URL: {e}", "warning")
        return None

# -----------------------------
# HYBRID PRICE FETCH
# -----------------------------
def get_price(product, page, state, site):

    # 1️⃣ Try DOM first
    price = extract_price(page)

    if price:
        log(state, f"{site}: ₹{price:,.0f}", "info")
        return price

    # 2️⃣ Fallback to Gemini (limited usage)
    log(
        state,
        f"{site}: Couldn't find price on page — using AI to analyze...",
        "warning"
)

    try:
        screenshot = page.screenshot()

        answer = ask_vision(
            screenshot,
            f"""
            What is the price of the first '{product}' result?

            Rules:
            - Return ONLY the number
            - No words, no sentences
            - Example: 52999
            """
            )

        match = re.search(r"\d[\d,]*", answer)

        if not match:
            raise ValueError(f"No number found in AI response: {answer}")

        price = float(match.group().replace(",", ""))

        log(state, f"🤖 {site} (AI): ₹{price}", "success")
        return price

    except Exception as e:
        if "429" in str(e):
            log(state, "⚠️ Unable to analyze further right now (limit reached)", "error")
        else:
            log(state, f"{site} failed: {e}", "warning")

        return None

# -----------------------------
# STEP 1: COMPARE PRICES
# -----------------------------
def compare_prices(product, page, state):

    #Get sites dynamically per product
    COMPARE_SITES = get_popular_sites(product, state)
    if not COMPARE_SITES:
        log(state, "⚠️ Using fallback hardcoded sites", "info")
        COMPARE_SITES = FALLBACK_SITES

    q = urllib.parse.quote(product)
    results = {}

    for site, url_tpl in COMPARE_SITES.items():
        try:
            url = url_tpl.format(q=q)

            log(state, f"🔎 Checking {site}...")
            page.goto(url, timeout=15000)
            page.wait_for_timeout(2000)
            
            # Scroll to load lazy content
            page.mouse.wheel(0, 300)
            page.wait_for_timeout(700)

            # Extract product URL from DOM
            product_url = extract_product_url_from_dom(page, state, site)
            
            # Get price
            price = get_price(product, page, state, site)

            if not price:
                continue

            results[site] = {"price": price, "search_url": url, "product_url": product_url}

        except Exception as e:
            log(state, f"{site} failed: {e}", "warning")

    if not results:
        return None

    best = min(results, key=lambda x: results[x]["price"])

    state["price_comparison"] = results
    state["best_site"] = best
    state["current_price"] = results[best]["price"]
    state["best_product_url"] = results[best].get("product_url")
    
    if state["best_product_url"]:
        log(state, f"🔗 Found product URL for {best}:{state['best_product_url']}", "info")
    else:
        log(state, f"⚠️ No product URL found for {best}, will use search URL", "warning")

    log(state, f"🏆 Cheapest: {best}", "success")

    # Return product URL if found, otherwise return search URL
    return results[best]["product_url"] if results[best]["product_url"] else results[best]["search_url"]

# -----------------------------
# NAVIGATE
# -----------------------------
def navigate(page, url, state, site):
    try:
        page.goto(url)
        log(state, f"🌐 Navigated to {site}")
    except Exception as e:
        log(state, f"Navigation failed: {e}", "error")   


def is_valid_discount(txt):
    txt = txt.lower()
    return bool(re.search(r"\d", txt))  # just needs a number

def prepare_page_for_ai(page, state):
    try:
        # Wait for stability
        page.wait_for_load_state("networkidle", timeout=5000)
    except:
        pass

    log(state, "🧠 Preparing page for AI...", "info")

    # 🔽 Scroll to offers section
    for _ in range(2):
        page.mouse.wheel(0, 1200)
        page.wait_for_timeout(1000)

    # 🔘 Click "Available offers"
    try:
        btn = page.locator("text=Available offers").first
        if btn.count() > 0:
            btn.click()
            page.wait_for_timeout(2000)
            log(state, "✅ Opened 'Available offers'", "info")
    except:
        pass

    # 🔘 Click "more offers"
    try:
        more = page.locator("text=more").first
        if more.count() > 0:
            more.click()
            page.wait_for_timeout(2000)
            log(state, "✅ Expanded more offers", "info")
    except:
        pass

    # 🔽 Extra scroll (important for lazy load)
    for _ in range(2):
        page.mouse.wheel(0, 1000)
        page.wait_for_timeout(1000)

    page.wait_for_timeout(1500)

def apply_coupons(page, state, codes):

    import re
    import json

    # -----------------------------
    # 💰 STEP 1: Base price
    # -----------------------------
    base_price = state.get("current_price", 0)
    state["base_price"] = base_price

    # 🧠 STEP 2: Prepare page for AI (NEW)
    prepare_page_for_ai(page, state)

    # -----------------------------
    # 🤖 STEP 3: AI extraction
    # -----------------------------
    try:
        screenshot = page.screenshot(full_page=True)

        result = ask_vision(
            screenshot,
            f"""
            Extract all offers from this product page.

            Base product price: ₹{base_price}

            Categorize into:
            - bank_offers
            - coupons
            - exchange_offers

            IGNORE:
            - EMI offers
            - financing options

            Rules:
            - Include discount text
            - ALSO estimate final price after applying the offer

            Return JSON:
            {{
            "bank_offers": [{{"bank":"","discount":"","final_price":""}}],
            "coupons": [{{"code":"","discount":"","final_price":""}}],
            "exchange_offers": [{{"discount":"","final_price":""}}]
            }}

            IMPORTANT:
            - Final price should be approximate
            - Return ONLY JSON
            """
        )

        # DEBUG
        log(state, f"🧠 AI RAW:\n{result}", "info")

        match = re.search(r"\{.*\}", result, re.DOTALL)
        if not match:
            log(state, "⚠️ No structured offers found", "warning")
            return

        data = json.loads(match.group())

    except Exception as e:
        log(state, f"⚠️ Offer extraction failed: {e}", "warning")
        return
      

    # STEP 4: CLEAN AI EXTRACTED OFFERS
    bank_offers = [b for b in data.get("bank_offers", []) if is_valid_discount(b.get("discount",""))]
    coupons = [c for c in data.get("coupons", []) if is_valid_discount(c.get("discount",""))]
    exchange_offers = [e for e in data.get("exchange_offers", []) if is_valid_discount(e.get("discount",""))]


    # -----------------------------
    # 🧠 STORE OFFERS (NEW)
    # -----------------------------
    state["offers"] = {
        "bank_offers": bank_offers,
        "coupons": coupons,
        "exchange_offers": exchange_offers
    }
    # -----------------------------
    # 🧾 STEP 5: LOG CLEAN OUTPUT
    # -----------------------------
    if bank_offers:
        log(state, f"🏦 Found {len(bank_offers)} bank offer(s)", "success")
        for b in bank_offers:
            log(state, f"   • {b.get('bank')} → {b.get('discount')}", "info")
    else:
        log(state, "ℹ️ No bank offers found", "info")

    if coupons:
        log(state, f"🎟 Found {len(coupons)} coupon(s)", "success")
        for c in coupons:
            log(state, f"   • {c.get('code')} → {c.get('discount')}", "info")
    else:
        log(state, "ℹ️ No coupons found", "info")

    if exchange_offers:
        log(state, f"🔄 Found {len(exchange_offers)} exchange offer(s)", "success")
        for e in exchange_offers:
            log(state, f"   • {e.get('discount')}", "info")
    else:
        log(state, "ℹ️ No exchange offers found", "info")    
    

# -----------------------------
# MAIN RUN
# -----------------------------
def run(product, goal, state, extra_codes=None):

    codes = (extra_codes or []) + DEFAULT_CODES

    import asyncio
    import sys

    
    with sync_playwright() as p:
        
        browser = p.chromium.launch_persistent_context(
            user_data_dir="user_data",
            headless=False
        )
        page = browser.new_page()

        state["agent_running"] = True

        try:
            url = compare_prices(product, page, state)

            if not url:
                log(state, "No prices found", "error")
                return

            navigate(page, url, state, state["best_site"])

            apply_coupons(page, state, codes)

            log(
                state,
                f"💰 Final Price: ₹{state['current_price']}",
                "success"
            )

        except Exception as e:
            log(state, f"Error: {e}", "error")

        finally:
            state["agent_running"] = False
            #browser.close()