# 🛒 PricePilot – AI Deal Finder

PricePilot is a Python + Streamlit app that helps you **find the cheapest prices online** for a product and **apply the best coupons or offers**. It uses AI (Gemini) to extract offers and performs dynamic price comparison across popular e-commerce sites like Amazon, Flipkart, Myntra, Ajio, and more.

---

## ⚡ Features

- Compare prices across multiple e-commerce sites
- Automatically pick the **lowest price**
- Extract and categorize offers:
  - Bank offers
  - Coupons
  - Exchange offers
- AI-based analysis for hard-to-read prices or offers
- Streamlit-based UI for live logs and results

---

## 📁 Project Structure

```
PricePilot/
│── app.py               # Main Streamlit app
│── gemini_agent.py      # Agent logic (search, scrape, AI)
│── requirements.txt     # Python dependencies
│── README.md            # Project instructions
│
├── venv/                # Virtual environment (not uploaded)
└── .streamlit/
    └── secrets.toml     # API key (NOT uploaded)
    └── secrets_example.toml # Sample template
```

---

## 🛠 Setup Instructions

### 1. Install Required Software

- **Python 3.10**: https://www.python.org/downloads/
- **VS Code**: https://code.visualstudio.com/
- **Git (optional)**: https://git-scm.com/downloads

---

### 2. Clone the project (or copy files)

```bash
git clone <your-repo-url>
cd PricePilot
```

---

### 3. Create and activate virtual environment

**Windows:**

```bash
py -3.10 -m venv venv
venv\Scripts\activate
```

**Mac/Linux:**

```bash
python3.10 -m venv venv
source venv/bin/activate
```

---

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

---

### 5. Install Playwright browsers

```bash
playwright install
```

---

### 6. Configure API Key (Gemini)

1. Copy `.streamlit/secrets_example.toml` → `.streamlit/secrets.toml`
2. Edit `.streamlit/secrets.toml`:

```toml
GEMINI_API_KEY = "your_api_key_here"
```

**⚠️ Do NOT upload `secrets.toml` to GitHub.**

---

### 7. Run the app

```bash
streamlit run app.py
```

Open in your browser:

```
http://localhost:8501
```

---

## 🧪 Demo Product Suggestions

- `iPhone 14 128GB`
- `Samsung Galaxy S21 FE`
- `boAt Airdopes 141`

These products are stable for demo and price extraction.
