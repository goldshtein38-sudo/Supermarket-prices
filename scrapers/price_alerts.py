"""
price_alerts.py — שמירת היסטוריה + שליחת התראות טלגרם על שינויי מחירים
מופעל אחרי scrape.py ו-build_html.py בכל הרצה שבועית
"""
import json, os, glob, sys
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
THRESHOLD = 3.0  # % שינוי מינימלי להתראה
PENDING_PATH = "/tmp/price_alert_pending.txt"

def price_kg(it):
    try:
        if it.get("is_weighted") and it.get("unit_price"):
            up = float(it["unit_price"])
            unit = it.get("unit", "") or ""
            if "100" in unit and "גר" in unit:
                return round(up * 10, 2)
            return round(up, 2)
        p = float(it["price"]); q = float(it.get("qty") or 0); unit = it.get("unit", "") or ""
        if q > 0 and "גר" in unit: return round(p / q * 1000, 2)
        if q > 0 and "ק" in unit and "ג" in unit: return round(p / q, 2)
        return round(p, 2)
    except: return None

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ No Telegram credentials"); return
    import urllib.request, urllib.parse
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "HTML"
    }).encode()
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read())
            print("Telegram:", resp.get("ok"))
    except Exception as e:
        print(f"Telegram error: {e}")

def queue_alert(msg):
    """שומר הודעה לשליחה מאוחרת — רק אחרי שה-commit מצליח, כדי למנוע התראות-רפאים על נתונים שלא נשמרו בפועל"""
    with open(PENDING_PATH, "w", encoding="utf-8") as f:
        f.write(msg)
    print(f"📝 Alert queued for sending after commit: {PENDING_PATH}")

def send_pending():
    """שולח הודעה שהמתינה לשליחה — נקרא רק אחרי commit מוצלח בוורקפלואו"""
    if not os.path.exists(PENDING_PATH):
        print("No pending alert to send")
        return
    with open(PENDING_PATH, encoding="utf-8") as f:
        msg = f.read()
    send_telegram(msg)
    os.remove(PENDING_PATH)
    print("✅ Pending alert sent and file cleared")

def load_prices(filepath):
    """טוען prices.json ומחזיר dict: {chain: {name: price_kg}}"""
    try:
        data = json.load(open(filepath, encoding="utf-8"))
        result = {}
        for chain_key, chain in data.get("chains", {}).items():
            result[chain_key] = {}
            for cat, items in chain.get("categories", {}).items():
                for it in items:
                    p = price_kg(it)
                    if p and p > 0:
                        result[chain_key][it["name"]] = {"price": p, "cat": cat}
        return result, data.get("updated", "")
    except Exception as e:
        print(f"Load error: {e}"); return {}, ""

def main():
    os.makedirs("output/history", exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")

    # 1. שמור snapshot היום
    current_path = "output/prices.json"
    if not os.path.exists(current_path):
        print("No prices.json found"); return
    snapshot_path = f"output/history/prices_{today}.json"
    import shutil
    shutil.copy(current_path, snapshot_path)
    print(f"✅ Saved snapshot: {snapshot_path}")

    # 2. מצא snapshot קודם להשוואה
    history = sorted(glob.glob("output/history/prices_*.json"))
    if len(history) < 2:
        print("⏳ First run — no previous data to compare")
        queue_alert(
            f"✅ <b>בוט מחירי סופר תענוג הופעל!</b>\n\n"
            f"📍 מעקב מחירים — סניפי כרמיאל\n"
            f"🔔 מכאן ואילך תקבל התראות על שינויים מעל {THRESHOLD}%\n"
            f"📅 עודכן: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        return

    prev_path = history[-2]
    print(f"📊 Comparing {prev_path} → {snapshot_path}")
    current_prices, cur_date = load_prices(current_path)
    prev_prices, prev_date = load_prices(prev_path)

    # 3. מצא שינויים משמעותיים
    changes = []
    chain_names = {"tivtaam": "טיב טעם", "keshet": "קשת"}

    for chain_key, chain_name in chain_names.items():
        cur = current_prices.get(chain_key, {})
        prv = prev_prices.get(chain_key, {})
        for name, cur_data in cur.items():
            if name not in prv: continue
            p_cur = cur_data["price"]; p_prv = prv[name]["price"]
            if p_prv <= 0: continue
            pct = (p_cur - p_prv) / p_prv * 100
            if abs(pct) >= THRESHOLD:
                changes.append({
                    "chain": chain_name, "name": name,
                    "cat": cur_data["cat"],
                    "prev": p_prv, "cur": p_cur, "pct": pct
                })

    # 4. שלח התראה
    if not changes:
        print("✅ No significant price changes this week")
        queue_alert(
            f"📊 <b>עדכון שבועי — מחירי כרמיאל</b>\n\n"
            f"✅ אין שינויי מחירים משמעותיים השבוע\n"
            f"📅 {datetime.now().strftime('%d.%m.%Y')}"
        )
        return

    # מיין: הגדולים ביותר קודם
    changes.sort(key=lambda x: abs(x["pct"]), reverse=True)

    up = [c for c in changes if c["pct"] > 0]
    down = [c for c in changes if c["pct"] < 0]

    msg = f"🔔 <b>שינויי מחירים השבוע — כרמיאל</b>\n📅 {datetime.now().strftime('%d.%m.%Y')}\n"

    if up:
        msg += f"\n📈 <b>עלו ({len(up)} מוצרים):</b>\n"
        for c in up[:8]:
            msg += f"  • {c['name'][:28]} ({c['chain']}) {c['prev']:.1f}←{c['cur']:.1f} <b>+{c['pct']:.1f}%</b>\n"
        if len(up) > 8:
            msg += f"  ...ועוד {len(up)-8}\n"

    if down:
        msg += f"\n📉 <b>ירדו ({len(down)} מוצרים):</b>\n"
        for c in down[:8]:
            msg += f"  • {c['name'][:28]} ({c['chain']}) {c['prev']:.1f}←{c['cur']:.1f} <b>{c['pct']:.1f}%</b>\n"
        if len(down) > 8:
            msg += f"  ...ועוד {len(down)-8}\n"

    print(f"📨 Queuing alert: {len(changes)} changes")
    queue_alert(msg)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--send-pending":
        send_pending()
    else:
        main()
