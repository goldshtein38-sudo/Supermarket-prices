"""
scrape.py — איסוף מחירים מטיב טעם וקשת טעמים, סניף כרמיאל
טיב טעם: StoreID 010 | קשת טעמים: StoreID 015
גישה: HTTPS דרך פורטל publishedprices (Cerberus web client)
"""
import os, json, gzip, re, traceback
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import xml.etree.ElementTree as ET
from datetime import datetime

BASE = "https://url.publishedprices.co.il"

CHAINS = {
    "tivtaam": {"name": "טיב טעם", "user": "TivTaam", "password": "",
                "chain_id": "7290873255550", "store": "010"},
    "keshet":  {"name": "קשת טעמים", "user": "Keshet", "password": "",
                "chain_id": "7290785400000", "store": "015"},
}

CATEGORIES = {
    "עוף": ["עוף", "פרגית", "שניצל", "כרעיים", "שוקיים", "כנפיים", "כבד עוף", "לב עוף"],
    "הודו": ["הודו"],
    "בקר": ["בקר", "עגל", "אנטריקוט", "סינתה", "פיקניה", "שייטל", "צ'אק", "צאך", "אסאדו"],
    "בשר לבן": ["חזיר"],
    "פסטרמות": ["פסטרמה", "שינקן", "שינקה", "קורנביף", "רוסטביף", "בייקון"],
    "נקניקים": ["נקניק", "סלמי", "פריזר", "סרוולד", "קבנוס", "מורטדלה"],
    "נקניקיות": ["נקניקיות", "וינר", "פרנקפורטר"],
    "גבינות": ["גבינ", "מוצרלה", "פרמזן", "גאודה", "בולגרית", "ריקוטה", "קממבר", "ברי"],
}
LOG = []
def log(s): LOG.append(str(s)); print(s)

def categorize(name):
    n = name.lower()
    for cat, kws in CATEGORIES.items():
        for kw in kws:
            if kw.lower() in n:
                return cat
    return None

def find_token(html):
    for p in [r'name=["\']csrftoken["\']\s+value=["\']([^"\']+)',
              r'<meta\s+name=["\']csrftoken["\']\s+content=["\']([^"\']+)',
              r'csrftoken["\']?\s*[:=]\s*["\']([^"\']+)']:
        m = re.search(p, html, re.IGNORECASE)
        if m: return m.group(1)
    return None

def login(session, user, password):
    r = session.get(f"{BASE}/login", timeout=30)
    token = find_token(r.text)
    payload = {"username": user, "password": password, "Submit": "Sign in"}
    if token: payload["csrftoken"] = token
    session.post(f"{BASE}/login/user", data=payload, timeout=30,
                 headers={"Referer": f"{BASE}/login"})
    # טוקן טרי מדף /file
    chk = session.get(f"{BASE}/file", timeout=30)
    return find_token(chk.text) or token

def list_files(session, token):
    data = {"sEcho":"1","iColumns":"5","sColumns":",,,,","iDisplayStart":"0",
            "iDisplayLength":"100000","mDataProp_0":"fname","sSearch":"","cd":"/"}
    if token: data["csrftoken"] = token
    r = session.post(f"{BASE}/file/json/dir", timeout=60, data=data,
                     headers={"Referer": f"{BASE}/file","X-CSRFToken":token or "",
                              "X-Requested-With":"XMLHttpRequest"})
    return [row.get("fname","") for row in r.json().get("aaData", [])]

def pick_store_file(files, chain_id, store):
    """בוחר את קובץ ה-PriceFull העדכני ביותר של הסניף הנתון"""
    # פורמט: PriceFull<chain>-<XXX>-<store>-<date>.gz  או  PriceFull<chain>-<store>-<date>.gz
    candidates = []
    for f in files:
        if "PriceFull" not in f or chain_id not in f:
            continue
        # מצא את מקטעי המספרים בין מקפים
        parts = f.replace(".gz","").split("-")
        # store יכול להופיע כאחד המקטעים (עם padding)
        seg_match = any(seg == store or seg.lstrip("0") == store.lstrip("0") for seg in parts[1:])
        if seg_match:
            candidates.append(f)
    if not candidates:
        return None
    # העדכני ביותר = השם הגדול ביותר לקסיקוגרפית (התאריך בשם)
    return sorted(candidates)[-1]

def download(session, filename):
    return session.get(f"{BASE}/file/d/{filename}", timeout=120).content

def process_chain(key, cfg):
    categorized = {c: [] for c in CATEGORIES}
    store_label = cfg["store"]
    log(f"\n{'='*60}\n{cfg['name']} ({cfg['user']}) store={cfg['store']}")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (price-compare)"})
    session.verify = False
    try:
        token = login(session, cfg["user"], cfg["password"])
        files = list_files(session, token)
        target = pick_store_file(files, cfg["chain_id"], cfg["store"])
        if not target:
            log(f"  ⚠ no PriceFull file for store {cfg['store']}")
            return categorized, store_label
        log(f"  Using: {target}")
        raw = download(session, target)
        try: content = gzip.decompress(raw)
        except Exception: content = raw
        try: root = ET.fromstring(content)
        except Exception: root = ET.fromstring(content.decode("utf-8-sig", errors="ignore"))

        sid_el = root.find(".//StoreID") or root.find(".//StoreId")
        if sid_el is not None and (sid_el.text or "").strip():
            store_label = sid_el.text.strip()

        items = root.findall(".//Item")
        cnt = 0
        for item in items:
            name = (item.findtext("ItemName") or "").strip()
            price = item.findtext("ItemPrice") or ""
            status = item.findtext("ItemStatus") or "1"
            if not (name and price) or status == "0":
                continue
            cat = categorize(name)
            if cat:
                categorized[cat].append({
                    "name": name,
                    "manufacturer": item.findtext("ManufactureName") or "",
                    "item_code": item.findtext("ItemCode") or "",
                    "price": price,
                    "unit_price": item.findtext("UnitOfMeasurePrice") or "",
                    "unit": item.findtext("UnitOfMeasure") or item.findtext("UnitQty") or "",
                    "is_weighted": (item.findtext("bIsWeighted") or "0") == "1",
                    "qty": item.findtext("Quantity") or "",
                })
                cnt += 1
        log(f"  Total Items: {len(items)} | Categorized: {cnt}")
        for c, lst in categorized.items():
            if lst: log(f"      {c}: {len(lst)}")
    except Exception as e:
        log(f"  ERROR: {e}\n{traceback.format_exc()}")
    return categorized, store_label

def main():
    os.makedirs("output", exist_ok=True)
    result = {"updated": datetime.now().strftime("%d.%m.%Y %H:%M"),
              "note": "נתונים מסניף כרמיאל",
              "stores": {"tivtaam": "010", "keshet": "015"},
              "chains": {}}
    try:
        for key, cfg in CHAINS.items():
            cats, store = process_chain(key, cfg)
            result["chains"][key] = {"name": cfg["name"], "store_id": store, "categories": cats}
    finally:
        with open("output/prices.json","w",encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        with open("output/diagnose_output.txt","w",encoding="utf-8") as f:
            f.write("\n".join(LOG))
        print("✅ done")

if __name__ == "__main__":
    main()
