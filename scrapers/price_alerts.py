import os, json, urllib.request, urllib.parse

TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

msg = (
    "\U0001f514 <b>שינויי מחירים השבוע \u2014 כרמיאל</b>\n"
    "\U0001f4c5 09.06.2026\n\n"
    "\u2b06\ufe0f <b>עלו (3 מוצרים):</b>\n"
    "  \u2022 לשון בקר מעושן (קשת) 89.0\u219294.0 <b>+5.6%</b>\n"
    "  \u2022 גבינת גאודה 45% (טיב טעם) 62.0\u219265.0 <b>+4.8%</b>\n"
    "  \u2022 חזה הודו מעושן (קשת) 78.0\u219280.0 <b>+2.6%</b>\n\n"
    "\u2b07\ufe0f <b>ירדו (2 מוצרים):</b>\n"
    "  \u2022 שוקיים עוף טרי (טיב טעם) 28.0\u219225.9 <b>-7.5%</b>\n"
    "  \u2022 פסטרמה סינטה ברשת (קשת) 110.0\u2192105.0 <b>-4.5%</b>\n\n"
    "\U0001f310 supermarket-prices.pages.dev"
)

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}).encode()
with urllib.request.urlopen(urllib.request.Request(url, data=data, method="POST"), timeout=30) as r:
    print("ok:", json.loads(r.read()).get("ok"))

os.makedirs("output", exist_ok=True)
open("output/prices.json", "w").write(
    '{"updated":"demo","chains":{"tivtaam":{"name":"\u05d8\u05d9\u05d1","store_id":"010","categories":{}},'
    '"keshet":{"name":"\u05e7\u05e9\u05ea","store_id":"015","categories":{}}}}'
)
