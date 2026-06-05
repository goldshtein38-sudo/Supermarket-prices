import os, json, urllib.request, urllib.parse

TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

msg = (
    "\U0001f514 <b>דוגמא — כך תיראה ההודעה כל יום שני</b>\n"
    "\U0001f4c5 09.06.2026\n\n"
    "\U0001f4c8 <b>עלו (3 מוצרים):</b>\n"
    "  \u2022 לשון בקר מעושן (קשת) \u20aa89.0\u2192\u20aa94.0 <b>+5.6%</b>\n"
    "  \u2022 גבינת גאודה 45% (טיב טעם) \u20aa62.0\u2192\u20aa65.0 <b>+4.8%</b>\n"
    "  \u2022 חזה הודו מעושן (קשת) \u20aa78.0\u2192\u20aa80.0 <b>+2.6%</b>\n\n"
    "\U0001f4c9 <b>ירדו (2 מוצרים):</b>\n"
    "  \u2022 שוקיים עוף טרי (טיב טעם) \u20aa28.0\u2192\u20aa25.9 <b>-7.5%</b>\n"
    "  \u2022 פסטרמה סינטה ברשת (קשת) \u20aa110.0\u2192\u20aa105.0 <b>-4.5%</b>\n\n"
    "\U0001f310 supermarket-prices.pages.dev"
)

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}).encode()
req = urllib.request.Request(url, data=data, method="POST")
with urllib.request.urlopen(req, timeout=30) as r:
    print("ok:", json.loads(r.read()).get("ok"))

# שמור prices.json ריק כדי שה-build_html לא יקרס
os.makedirs("output", exist_ok=True)
open("output/prices.json", "w").write(
    '{"updated":"demo","chains":{"tivtaam":{"name":"\u05d8\u05d9\u05d1 \u05d8\u05e2\u05dd","store_id":"010","categories":{}},'
    '"keshet":{"name":"\u05e7\u05e9\u05ea","store_id":"015","categories":{}}}}'
)
