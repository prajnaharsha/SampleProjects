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
    Suggest 4 most popular Indian e-commerce websites for buying '{product}'.
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

    IMPORTANT:
    - If the site is one of these, you MUST use the EXACT URL pattern:

        Amazon: https://www.amazon.in/s?k={{q}}
        Flipkart: https://www.flipkart.com/search?q={{q}}
        Reliance Digital: https://www.reliancedigital.in/products?q={{q}}
        Croma: https://www.croma.com/searchB?q={{q}}%3Arelevance
        Myntra: https://www.myntra.com/{{q}}
        Ajio: https://www.ajio.com/search/?text={{q}}
        BigBasket: https://www.bigbasket.com/ps/?q={{q}}
        Blinkit: https://blinkit.com/s/?q={{q}}
        Zepto: https://www.zeptonow.com/search?query={{q}}
        JioMart: https://www.jiomart.com/search/{{q}}
    - If you choose ANY of the above sites, DO NOT modify their URL format
    - For other websites, generate a valid search URL using {{q}}

    EXLCDUE Flipkart

    """

    if "action_log" not in state:
        state["action_log"] = []

    try:
        res = client.models.generate_content(
            model="models/gemini-2.5-flash-lite",
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
        if "429" in str(e):
            log(state, "⚠️ Popular sites unavailable: AI limit reached", "warning")
        else:
            log(state, f"⚠️ Popular sites unavailable: {str(e)}", "warning")
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
        page.wait_for_timeout(2000)

        # 👇 AND THIS (VERY IMPORTANT)
        page.mouse.wheel(0, 800)
        page.wait_for_timeout(1500)
    except:
        pass    
   

    selectors = [
        # Flipkart (product page)
        "div._30jeq3._16Jk6d",
        "div._30jeq3",
        "div.Nx9bqj",
        "div[class*='Nx9bqj']",

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

        # -----------------------------
        # JioMart
        # -----------------------------
        "span.jm-price",
        "div.plp-card-details-price",
        "div[class*='price'] span",

        # -----------------------------
        # Myntra
        # -----------------------------
        "span.pdp-price",
        "span.pdp-discounted-price",
        "div.product-price span",

        # -----------------------------
        # Ajio
        # -----------------------------
        "span.price",
        "div.price strong",
        "span.discounted-price",

        "span.DiscountedPrice___StyledSpan2-sc-1qdt4xj-1",
        "span[class*='DiscountedPrice']",
        "div.sku-item-price",
        "span[class*='Price']",
        "h4[class*='price']",

        # Generic
        "span.price",
        ".product-price",
        "span[data-price]",
        "div.price-section span",
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

            page.mouse.wheel(0, 300)
            page.wait_for_timeout(700)

            product_url = extract_product_url_from_dom(page, state, site)
            price = get_price(product, page, state, site)

            if not price:
                continue

            results[site] = {
                "price": price,
                "search_url": url,
                "product_url": product_url
            }

        except Exception as e:
            log(state, f"{site} failed: {e}", "warning")

    if not results:
        return None

    # 🔥 NEW: pick top 2 cheapest
    sorted_sites = sorted(results.items(), key=lambda x: x[1]["price"])
    top2 = sorted_sites[:2]

    state["top2_sites"] = {
        site: data for site, data in top2
    }

    # Prepare structure
    state["selected_sites"] = {}
    for site, data in state["top2_sites"].items():
        state["selected_sites"][site] = {
            "price": data["price"],
            "product_url": data.get("product_url"),
            "search_url": data.get("search_url"),
            "offers": {}
        }

    log(state, f"🏆 Top 2: {', '.join(state['top2_sites'].keys())}", "success")

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


def normalize(text):
    if not text:
        return ""
    text = text.lower()
    text = text.replace("₹", "")
    text = text.replace(",", "")
    text = text.replace("upto", "up to")
    text = text.replace("  ", " ")
    return text.strip()


def is_duplicate(a, b):
    return normalize(a) == normalize(b)


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
    def get_raw_text(res):
        try:
            return res.candidates[0].content.parts[0].text
        except:
            return res.text  # fallback
        import re

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

        log(state, f"✅ RAW AI Response: {res.text}", "success")        

        return data

    except Exception as e:
        if "429" in str(e):
            log(state, "⚠️ HTML extraction failed: AI limit reached", "warning")
        else:
            log(state, "⚠️ HTML extraction failed: Could not fetch data from AI", "warning")
        return None
    
def apply_coupons(page, state, codes):

    base_price = state.get("current_price", 0)
    product = state.get("product", "product")
    site = state.get("best_site", "Amazon")

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
    # 🥈 NO  OFFERS
    # -----------------------------
    if not has_offers(data):
        log(state, "ℹ️ No offers found on page", "info")
        data = {
            "bank_offers": [],
            "coupons": [],
            "exchange_offers": []
        }  
        
    #log(state, f"🧪 Raw AI offers: {json.dumps(data)}", "info")
    # -----------------------------
    # 🧹 CLEAN + STORE
    # -----------------------------
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

        2. Product Insight:
        - Is this product generally good?
        - Any known pros/cons
        - Who should buy it

        Rules:
        - Max 6-7 lines total
        - Be crisp and practical
        - No fluff

        Output format:

        Deal Insight:
        ...

        Product Insight:
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
def run(product, goal, state, extra_codes=None):

    codes = (extra_codes or []) + DEFAULT_CODES

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

                apply_coupons(page, state, codes)

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