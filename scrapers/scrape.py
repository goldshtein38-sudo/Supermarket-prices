"""
scrape.py עמיד לשגיאות — שומר אבחון מפורט ולא קורס
"""
import os, json, gzip, io, ftplib, traceback
import xml.etree.ElementTree as ET
from datetime import datetime

CHAINS = {
    "tivtaam": {"name": "טיב טעם", "ftp_host": "url.retail.publishedprices.co.il",
                "ftp_user": "TivTaam", "ftp_pass": "", "chain_id": "7290873255550"},
    "keshet":  {"name": "קשת טעמים", "ftp_host": "url.retail.publishedprices.co.il",
                "ftp_user": "Keshet", "ftp_pass": "", "chain_id": "7290785400000"},
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
    LOG.append(str(s)); print(s)

def save_log():
    os.makedirs("output", exist_ok=True)
    with open("output/diagnose_output.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(LOG))

def categorize(name):
    n = name.lower()
    for cat, kws in CATEGORIES.items():
        for kw in kws:
            if kw.lower() in n:
                return cat
    return None

def process_chain(key, cfg):
    categorized = {c: [] for c in CATEGORIES}
    store_label = None
    log(f"\n{'='*60}\n{cfg['name']} ({cfg['ftp_user']})")
    try:
        ftp = ftplib.FTP(cfg["ftp_host"], timeout=60)
        ftp.login(cfg["ftp_user"], cfg["ftp_pass"])
        log("  FTP connected")
    except Exception as e:
        log(f"  FTP login FAILED: {e}")
        return categorized, store_label

    try:
        ftp.cwd("/"); entries = []; ftp.dir(entries.append)
        pf = [e.split()[-1] for e in entries if "PriceFull" in e.split()[-1] and cfg["chain_id"] in e.split()[-1]]
        log(f"  PriceFull files matching chain_id: {len(pf)}")
        # אם אין התאמה ל-chain_id, נסה כל PriceFull
        if not pf:
            pf = [e.split()[-1] for e in entries if "PriceFull" in e.split()[-1]]
            log(f"  (fallback) any PriceFull files: {len(pf)}")
        for f in pf[:8]:
            log(f"    {f}")
        if not pf:
            ftp.quit(); return categorized, store_label

        target = pf[0]
        log(f"  Using: {target}")
        buf = io.BytesIO(); ftp.retrbinary(f"RETR {target}", buf.write); ftp.quit()
        buf.seek(0)
        raw = buf.read()
        log(f"  Downloaded bytes: {len(raw)}")
        # נסה gzip
        try:
            content = gzip.decompress(raw)
            log("  decompressed gzip OK")
        except Exception:
            content = raw
            log("  not gzip, using raw")

        # נסה לפרסר
        try:
            root = ET.fromstring(content)
        except Exception as e:
            # אולי יש BOM/קידוד — נסה דרך טקסט
            log(f"  fromstring failed: {e}; trying decode")
            txt = content.decode("utf-8-sig", errors="ignore")
            root = ET.fromstring(txt)

        log(f"  Root tag: {root.tag}")
        for ch in list(root):
            if ch.tag.lower().startswith("store") and (ch.text or "").strip():
                store_label = (ch.text or "").strip()
                log(f"    root <{ch.tag}> = {store_label}")
        first = root.find(".//Item")
        if first is not None:
            log(f"  First Item fields: {[c.tag for c in first]}")
        items = root.findall(".//Item")
        log(f"  Total Items: {len(items)}")

        cnt = 0
        for item in items:
            name = (item.findtext("ItemName") or item.findtext("ItemNm") or "").strip()
            price = item.findtext("ItemPrice") or ""
            if not (name and price):
                continue
            cat = categorize(name)
            if cat:
                categorized[cat].append({
                    "name": name,
                    "manufacturer": item.findtext("ManufacturerName") or item.findtext("ManufacturerItemDescription") or "",
                    "item_code": item.findtext("ItemCode") or "",
                    "price": price,
                    "unit_price": item.findtext("UnitOfMeasurePrice") or "",
                    "unit": item.findtext("UnitOfMeasure") or item.findtext("UnitQty") or "",
                    "is_weighted": (item.findtext("bIsWeighted") or "0") == "1",
                    "qty": item.findtext("Quantity") or "",
                })
                cnt += 1
        log(f"  Categorized: {cnt}")
    except Exception as e:
        log(f"  ERROR: {e}")
        log(traceback.format_exc())
    return categorized, store_label

def main():
    os.makedirs("output", exist_ok=True)
    result = {"updated": datetime.now().strftime("%d.%m.%Y %H:%M"),
              "note": "נתונים מסניף כרמיאל בלבד", "chains": {}}
    try:
        for key, cfg in CHAINS.items():
            cats, store = process_chain(key, cfg)
            result["chains"][key] = {"name": cfg["name"], "store_id": store or "?", "categories": cats}
    except Exception as e:
        log(f"FATAL: {e}\n{traceback.format_exc()}")
    finally:
        with open("output/prices.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        save_log()
        log("\n✅ done")

if __name__ == "__main__":
    main()
