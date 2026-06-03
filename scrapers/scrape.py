"""
סקריפט לאיסוף מחירים מטיב טעם וקשת טעמים — סניף כרמיאל
"""

import os
import json
import gzip
import xml.etree.ElementTree as ET
import ftplib
import io
import re
from datetime import datetime

# ─────────────────────────────────────────
# הגדרות
# ─────────────────────────────────────────

CHAINS = {
    "tivtaam": {
        "name": "טיב טעם",
        "ftp_host": "url.retail.publishedprices.co.il",
        "ftp_user": "TivTaam",
        "ftp_pass": "",
        "chain_id": "7290873255550",
        "store_id": "3152",  # סניף כרמיאל
    },
    "keshet": {
        "name": "קשת טעמים",
        "ftp_host": "url.retail.publishedprices.co.il",
        "ftp_user": "Keshet",
        "ftp_pass": "",
        "chain_id": "7290785400000",
        "store_id": "1500",  # סניף כרמיאל
    },
}

# קטגוריות שרוצים לשמור (לפי ItemName contains)
CATEGORIES = {
    "עוף": ["עוף", "פרגית", "שניצל", "כרעיים", "שוקיים", "כנפיים", "כבד עוף", "לב עוף"],
    "הודו": ["הודו"],
    "בקר": ["בקר", "עגל", "אנטריקוט", "סינתה", "פיקניה", "שייטל", "צ'אק", "צאך", "אסאדו"],
    "בשר לבן": ["לבן", "חזיר"],
    "פסטרמות": ["פסטרמה", "שינקן", "שינקה", "דקניקים", "קורנביף", "רוסטביף", "בייקון"],
    "נקניקים": ["נקניק", "סלמי", "פריזר", "סרוולד", "קבנוס", "מורטדלה"],
    "נקניקיות": ["נקניקיות", "וינר", "פרנקפורטר"],
    "גבינות": ["גבינ", "מוצרלה", "פרמזן", "גאודה", "בולגרית", "ריקוטה"],
}

OUTPUT_FILE = "output/prices.json"

# ─────────────────────────────────────────
# גישה ל-FTP וקריאת קבצי XML
# ─────────────────────────────────────────

def connect_ftp(chain_config):
    """מתחבר ל-FTP ומחזיר session"""
    ftp = ftplib.FTP(chain_config["ftp_host"])
    ftp.login(chain_config["ftp_user"], chain_config["ftp_pass"])
    return ftp

def list_price_files(ftp, chain_id):
    """מחזיר רשימת קבצי PriceFull מה-FTP"""
    files = []
    try:
        ftp.cwd("/")
        entries = []
        ftp.dir(entries.append)

        for entry in entries:
            parts = entry.split()
            if not parts:
                continue
            filename = parts[-1]
            if "PriceFull" in filename and chain_id in filename:
                files.append(filename)
    except Exception as e:
        print(f"Error listing files: {e}")

    return files

def download_and_parse(ftp, filename):
    """מוריד קובץ XML גזיפ ומנתח אותו"""
    buf = io.BytesIO()
    try:
        ftp.retrbinary(f"RETR {filename}", buf.write)
    except Exception as e:
        print(f"Error downloading {filename}: {e}")
        return []

    buf.seek(0)

    try:
        # נסה לפתוח כגזיפ
        with gzip.open(buf, 'rb') as f:
            content = f.read()
    except Exception:
        buf.seek(0)
        content = buf.read()

    try:
        root = ET.fromstring(content)
    except Exception as e:
        print(f"XML parse error for {filename}: {e}")
        return []

    items = []
    for item in root.iter("Item"):
        name = (item.findtext("ItemName") or "").strip()
        price = item.findtext("ItemPrice") or ""
        unit_price = item.findtext("UnitOfMeasurePrice") or ""
        unit = item.findtext("UnitOfMeasure") or ""
        is_weighted = item.findtext("bIsWeighted") or "0"
        manufacturer = item.findtext("ManufacturerName") or ""
        item_code = item.findtext("ItemCode") or ""
        qty = item.findtext("Quantity") or ""
        store_id = item.findtext("StoreID") or ""

        if name and price:
            items.append({
                "name": name,
                "manufacturer": manufacturer,
                "item_code": item_code,
                "price": price,
                "unit_price": unit_price,
                "unit": unit,
                "is_weighted": is_weighted == "1",
                "qty": qty,
                "store_id": store_id,
            })

    return items

# ─────────────────────────────────────────
# סינון לפי קטגוריות וסניף
# ─────────────────────────────────────────

def categorize_item(item):
    """מחזיר קטגוריה למוצר או None"""
    name = item["name"].lower()
    for category, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw.lower() in name:
                return category
    return None

def filter_items(items, target_store_id=None):
    """מסנן ומחלק מוצרים לקטגוריות
    אם target_store_id נתון, יוצר מוצרים רק מהסניף הספציפי
    """
    categorized = {cat: [] for cat in CATEGORIES}

    for item in items:
        # אם צריך סניף ספציפי, בדוק שהמוצר מהסניף הזה
        if target_store_id and item.get("store_id") != target_store_id:
            continue
        
        cat = categorize_item(item)
        if cat:
            categorized[cat].append(item)

    return categorized

# ─────────────────────────────────────────
# הרצה ראשית
# ─────────────────────────────────────────

def scrape_chain(chain_key, chain_config):
    """גורד רשת אחת ומחזיר מוצרים מסווגים"""
    print(f"\n{'='*60}")
    print(f"Scraping {chain_config['name']} — סניף {chain_config.get('store_id', 'לא מוגדר')}")

    try:
        ftp = connect_ftp(chain_config)
        print(f"✓ Connected to FTP")
    except Exception as e:
        print(f"✗ FTP connection failed: {e}")
        return {}

    files = list_price_files(ftp, chain_config["chain_id"])
    print(f"✓ Found {len(files)} PriceFull files")

    if not files:
        ftp.quit()
        return {}

    # קח את הקובץ הראשון (או היחיד בדרך כלל)
    filename = files[0]
    print(f"✓ Downloading: {filename}")

    items = download_and_parse(ftp, filename)
    ftp.quit()

    print(f"✓ Parsed {len(items)} total items")

    # סנן לפי סניף כרמיאל
    target_store = chain_config.get("store_id")
    categorized = filter_items(items, target_store_id=target_store)
    total = sum(len(v) for v in categorized.values())
    print(f"✓ Categorized {total} items from store {target_store}")

    return categorized

def main():
    os.makedirs("output", exist_ok=True)

    result = {
        "updated": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "note": "נתונים מסניף כרמיאל בלבד",
        "stores": {
            "tivtaam": "3152",
            "keshet": "1500",
        },
        "chains": {}
    }

    for chain_key, chain_config in CHAINS.items():
        categorized = scrape_chain(chain_key, chain_config)
        result["chains"][chain_key] = {
            "name": chain_config["name"],
            "store_id": chain_config.get("store_id"),
            "categories": categorized
        }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Saved to {OUTPUT_FILE}")
    print(f"   עודכן: {result['updated']}")
    print(f"   טיב טעם סניף {result['stores']['tivtaam']}")
    print(f"   קשת סניף {result['stores']['keshet']}")

if __name__ == "__main__":
    main()
