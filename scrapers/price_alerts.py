
import os, json, urllib.request, urllib.parse
TOKEN=os.environ.get("TELEGRAM_TOKEN","")
CHAT_ID=os.environ.get("TELEGRAM_CHAT_ID","")
msg = "🔔 <b>דוגמא — כך תיראה ההודעה כל יום שני</b>
📅 09.06.2026

📈 <b>עלו (3 מוצרים):</b>
  • לשון בקר מעושן (קשת) ₪89→₪94 <b>+5.6%</b>
  • גבינת גאודה 45% (טיב טעם) ₪62→₪65 <b>+4.8%</b>
  • חזה הודו מעושן (קשת) ₪78→₪80 <b>+2.6%</b>

📉 <b>ירדו (2 מוצרים):</b>
  • שוקיים עוף טרי (טיב טעם) ₪28.0→₪25.9 <b>-7.5%</b>
  • פסטרמה סינטה ברשת (קשת) ₪110→₪105 <b>-4.5%</b>

🌐 supermarket-prices.pages.dev"
url=f"https://api.telegram.org/bot{TOKEN}/sendMessage"
data=urllib.parse.urlencode({"chat_id":CHAT_ID,"text":msg,"parse_mode":"HTML"}).encode()
req=urllib.request.Request(url,data=data,method="POST")
with urllib.request.urlopen(req,timeout=30) as r:
    print("ok:",__import__("json").loads(r.read()).get("ok"))
