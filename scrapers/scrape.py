"""
scrape.py עם אבחון מובנה — שומר diagnose_output.txt לתוך output/
"""
import os, json, gzip, io, ftplib
import xml.etree.ElementTree as ET
from datetime import datetime

CHAINS = {
    "tivtaam": {"name": "טיב טעם", "ftp_host": "url.retail.publishedprices.co.il",
                "ftp_user": "TivTaam", "ftp_pass": "", "chain_id": "7290873255550", "store_id": "3152"},
    "keshet":  {"name": "קשת טעמים", "ftp_host": "url.retail.publishedprices.co.il",
                "ftp_user": "Keshet", "ftp_pass": "", "chain_id": "7290785400000", "store_id": "1500"},
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
def log(s):
    LOG.append(str(s))
    print(s)

def categorize(name):
    n = name.lower()
    for cat, kws in CATEGORIES.items():
        for kw in kws:
            if kw.lower() in n:
                return cat
    return None

def main():
    os.makedirs("output", exist_ok=True)
    result = {"updated": datetime.now().strftime("%d.%m.%Y %H:%M"),
              "note": "נתונים מסניף כרמיאל בלבד",
              "stores": {"tivtaam": "3152", "keshet": "1500"}, "chains": {}}

    for key, cfg in CHAINS.items():
        log(f"\n{'='*60}\n{cfg['name']} ({cfg['ftp_user']}) target store={cfg['store_id']}")
        categorized = {c: [] for c in CATEGORIES}
        try:
            ftp = ftplib.FTP(cfg["ftp_host"]); ftp.login(cfg["ftp_user"], cfg["ftp_pass"])
        except Exception as e:
            log(f"  FTP login failed: {e}")
            result["chains"][key] = {"name": cfg["name"], "store_id": cfg["store_id"], "categories": categorized}
            continue

        ftp.cwd("/"); entries = []; ftp.dir(entries.append)
        pf = [e.split()[-1] for e in entries if "PriceFull" in e.split()[-1] and cfg["chain_id"] in e.split()[-1]]
        log(f"  PriceFull files: {len(pf)}")
        for f in pf[:6]:
            log(f"    {f}")
        if not pf:
            ftp.quit()
            result["chains"][key] = {"name": cfg["name"], "store_id": cfg["store_id"], "categories": categorized}
            continue

        # מצא קובץ ששמו מכיל את מספר הסניף, אחרת קח ראשון
        target = None
        for f in pf:
            if cfg["store_id"] in f:
                target = f; break
        if not target:
            target = pf[0]
            log(f"  ⚠ no file matched store {cfg['store_id']} in filename, using first")
        log(f"  Using file: {target}")

        buf = io.BytesIO(); ftp.retrbinary(f"RETR {target}", buf.write); ftp.quit(); buf.seek(0)
        try:
            content = gzip.open(buf, 'rb').read()
        except Exception:
            buf.seek(0); content = buf.read()
        root = ET.fromstring(content)

        # אבחון מבנה
        log(f"  Root tag: {root.tag}")
        root_store = None
        for ch in list(root):
            t = (ch.text or "").strip()
            if ch.tag in ("StoreId","StoreID","Store_Id") and t:
                root_store = t
                log(f"    root <{ch.tag}> = {t}")
        first = root.find(".//Item")
        if first is not None:
            log(f"  First Item fields: {[c.tag for c in first]}")

        items = root.findall(".//Item")
        log(f"  Total items in file: {len(items)}")

        # קטלג הכל (הקובץ כבר של סניף בודד, אין צורך לסנן לפי store id בתוך item)
        cnt = 0
        for item in items:
            name = (item.findtext("ItemName") or "").strip()
            price = item.findtext("ItemPrice") or ""
            if not (name and price):
                continue
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
        result["chains"][key] = {"name": cfg["name"], "store_id": root_store or cfg["store_id"], "categories": categorized}

    with open("output/prices.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    with open("output/diagnose_output.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(LOG))
    log("\n✅ Saved output/prices.json + diagnose_output.txt")

if __name__ == "__main__":
    main()
