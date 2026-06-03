"""
scrape.py — חיבור FTPS passive mode לשרת publishedprices
מנסה כמה שיטות חיבור עד שאחת עובדת
"""
import os, json, gzip, io, ftplib, ssl, traceback
import xml.etree.ElementTree as ET
from datetime import datetime

CHAINS = {
    "tivtaam": {"name": "טיב טעם", "ftp_user": "TivTaam", "ftp_pass": "", "chain_id": "7290873255550"},
    "keshet":  {"name": "קשת טעמים", "ftp_user": "Keshet", "ftp_pass": "", "chain_id": "7290785400000"},
}
HOST = "url.retail.publishedprices.co.il"
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

def make_connection(user, pw):
    """מנסה כמה שיטות: FTPS passive, FTP passive"""
    # שיטה 1: FTPS (explicit TLS) passive
    try:
        log("    trying FTPS (explicit TLS) passive...")
        ftps = ftplib.FTP_TLS(HOST, timeout=60)
        ftps.login(user, pw)
        ftps.prot_p()
        ftps.set_pasv(True)
        # בדיקה שעובד
        ftps.voidcmd("TYPE I")
        log("    FTPS passive OK")
        return ftps
    except Exception as e:
        log(f"    FTPS failed: {e}")
    # שיטה 2: FTP רגיל passive
    try:
        log("    trying plain FTP passive...")
        ftp = ftplib.FTP(HOST, timeout=60)
        ftp.login(user, pw)
        ftp.set_pasv(True)
        ftp.voidcmd("TYPE I")
        log("    FTP passive OK")
        return ftp
    except Exception as e:
        log(f"    FTP passive failed: {e}")
    return None

def list_files(conn):
    """מנסה NLST ואז MLSD"""
    names = []
    try:
        names = conn.nlst()
        log(f"    NLST returned {len(names)} entries")
    except Exception as e:
        log(f"    NLST failed: {e}")
    return names

def process_chain(key, cfg):
    categorized = {c: [] for c in CATEGORIES}
    store_label = None
    log(f"\n{'='*60}\n{cfg['name']} ({cfg['ftp_user']})")
    conn = make_connection(cfg["ftp_user"], cfg["ftp_pass"])
    if not conn:
        log("  could not connect with any method")
        return categorized, store_label
    try:
        try: conn.cwd("/")
        except Exception: pass
        names = list_files(conn)
        pf = [n.split("/")[-1] for n in names if "PriceFull" in n and cfg["chain_id"] in n]
        if not pf:
            pf = [n.split("/")[-1] for n in names if "PriceFull" in n]
            log(f"    (fallback) any PriceFull: {len(pf)}")
        log(f"  PriceFull files: {len(pf)}")
        for f in pf[:8]: log(f"    {f}")
        if not pf:
            log(f"  sample of all entries: {names[:10]}")
            conn.quit(); return categorized, store_label

        target = pf[0]
        log(f"  Using: {target}")
        buf = io.BytesIO(); conn.retrbinary(f"RETR {target}", buf.write)
        try: conn.quit()
        except Exception: pass
        raw = buf.getvalue()
        log(f"  bytes: {len(raw)}")
        try: content = gzip.decompress(raw); log("  gunzip OK")
        except Exception: content = raw; log("  not gzip")
        try: root = ET.fromstring(content)
        except Exception:
            root = ET.fromstring(content.decode("utf-8-sig", errors="ignore"))
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
