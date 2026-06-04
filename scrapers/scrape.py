"""
scrape.py — גישת HTTPS לפורטל publishedprices (Cerberus web client)
זו השיטה האמינה: login → file/json/dir → download
"""
import os, json, gzip, io, re, traceback
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import xml.etree.ElementTree as ET
from datetime import datetime

BASE = "https://url.publishedprices.co.il"

CHAINS = {
    "tivtaam": {"name": "טיב טעם", "user": "TivTaam", "password": "", "chain_id": "7290873255550"},
    "keshet":  {"name": "קשת טעמים", "user": "Keshet", "password": "", "chain_id": "7290785400000"},
}
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
LOG = []
def log(s): LOG.append(str(s)); print(s)

def categorize(name):
    n = name.lower()
    for cat, kws in CATEGORIES.items():
        for kw in kws:
            if kw.lower() in n: return cat
    return None

def login(session, user, password):
    """התחברות לפורטל. מושך csrftoken מדף הlogin"""
    r = session.get(f"{BASE}/login", timeout=30)
    # חפש csrftoken
    token = None
    m = re.search(r'name="csrftoken"\s+value="([^"]+)"', r.text)
    if m: token = m.group(1)
    else:
        m = re.search(r'csrftoken["\']?\s*[:=]\s*["\']([^"\']+)', r.text)
        if m: token = m.group(1)
    log(f"    csrftoken: {'found' if token else 'NOT found'}")
    payload = {"username": user, "password": password}
    if token: payload["csrftoken"] = token
    r = session.post(f"{BASE}/login/user", data=payload, timeout=30,
                     headers={"Referer": f"{BASE}/login"})
    log(f"    login status: {r.status_code}")
    return r.status_code == 200

def list_files(session, chain_id):
    """מקבל רשימת קבצים דרך file/json/dir"""
    r = session.post(f"{BASE}/file/json/dir", timeout=30,
                     data={"sd": "/", "DT_RowId": "", "iDisplayLength": "100000"},
                     headers={"Referer": f"{BASE}/file"})
    log(f"    dir status: {r.status_code}")
    try:
        data = r.json()
    except Exception:
        log(f"    dir not JSON, head: {r.text[:200]}")
        return []
    rows = data.get("aaData", data.get("data", []))
    names = []
    for row in rows:
        fn = row.get("fname") or row.get("name") or ""
        if fn: names.append(fn)
    log(f"    total files listed: {len(names)}")
    pf = [n for n in names if "PriceFull" in n and chain_id in n]
    if not pf:
        pf = [n for n in names if "PriceFull" in n]
    return pf

def download(session, filename):
    r = session.get(f"{BASE}/file/d/{filename}", timeout=120)
    return r.content

def process_chain(key, cfg):
    categorized = {c: [] for c in CATEGORIES}
    store_label = None
    log(f"\n{'='*60}\n{cfg['name']} ({cfg['user']})")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (price-compare)"})
    session.verify = False
    try:
        if not login(session, cfg["user"], cfg["password"]):
            log("    login failed"); return categorized, store_label
        pf = list_files(session, cfg["chain_id"])
        log(f"  PriceFull files: {len(pf)}")
        for f in pf[:8]: log(f"    {f}")
        if not pf: return categorized, store_label
        target = pf[0]
        log(f"  Using: {target}")
        raw = download(session, target)
        log(f"  bytes: {len(raw)}")
        try: content = gzip.decompress(raw); log("  gunzip OK")
        except Exception: content = raw; log("  not gzip")
        try: root = ET.fromstring(content)
        except Exception: root = ET.fromstring(content.decode("utf-8-sig", errors="ignore"))
        log(f"  Root: {root.tag}")
        for ch in list(root):
            if ch.tag.lower().startswith("store") and (ch.text or "").strip():
                store_label = ch.text.strip(); log(f"    <{ch.tag}> = {store_label}")
        first = root.find(".//Item")
        if first is not None: log(f"  Item fields: {[c.tag for c in first]}")
        items = root.findall(".//Item")
        log(f"  Total Items: {len(items)}")
        cnt = 0
        for item in items:
            name = (item.findtext("ItemName") or "").strip()
            price = item.findtext("ItemPrice") or ""
            if not (name and price): continue
            cat = categorize(name)
            if cat:
                categorized[cat].append({
                    "name": name,
                    "manufacturer": item.findtext("ManufacturerName") or "",
                    "item_code": item.findtext("ItemCode") or "",
                    "price": price,
                    "unit_price": item.findtext("UnitOfMeasurePrice") or "",
                    "unit": item.findtext("UnitOfMeasure") or "",
                    "is_weighted": (item.findtext("bIsWeighted") or "0") == "1",
                    "qty": item.findtext("Quantity") or "",
                })
                cnt += 1
        log(f"  Categorized: {cnt}")
    except Exception as e:
        log(f"  ERROR: {e}\n{traceback.format_exc()}")
    return categorized, store_label

def main():
    os.makedirs("output", exist_ok=True)
    result = {"updated": datetime.now().strftime("%d.%m.%Y %H:%M"), "note":"סניף כרמיאל", "chains":{}}
    try:
        for key, cfg in CHAINS.items():
            cats, store = process_chain(key, cfg)
            result["chains"][key] = {"name": cfg["name"], "store_id": store or "?", "categories": cats}
    finally:
        with open("output/prices.json","w",encoding="utf-8") as f: json.dump(result,f,ensure_ascii=False,indent=2)
        with open("output/diagnose_output.txt","w",encoding="utf-8") as f: f.write("\n".join(LOG))
        print("done")

if __name__ == "__main__": main()
