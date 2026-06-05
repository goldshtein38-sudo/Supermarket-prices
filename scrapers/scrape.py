import os, json, urllib.request, urllib.parse

TOKEN=os.environ.get("TELEGRAM_TOKEN","")
CHAT_ID=os.environ.get("TELEGRAM_CHAT_ID","")

msg = """🔔 <b>דוגמא — שינויי מחירים שבועיים</b>
📅 09.06.2026 (כך תיראה ההודעה מהשבוע הבא)

📈 <b>עלו (3 מוצרים):</b>
  • לשון בקר מעושן (קשת) ₪89.0→₪94.0 <b>+5.6%</b>
  • גבינת גאודה 45% (טיב טעם) ₪62.0→₪65.0 <b>+4.8%</b>
  • חזה הודו מעושן (קשת) ₪78.0→₪80.0 <b>+2.6%</b>

📉 <b>ירדו (2 מוצרים):</b>
  • שוקיים עוף טרי (טיב טעם) ₪28.0→₪25.9 <b>-7.5%</b>
  • פסטרמה סינטה ברשת (קשת) ₪110.0→₪105.0 <b>-4.5%</b>

🌐 supermarket-prices.pages.dev"""

url=f"https://api.telegram.org/bot{TOKEN}/sendMessage"
data=urllib.parse.urlencode({"chat_id":CHAT_ID,"text":msg,"parse_mode":"HTML"}).encode()
req=urllib.request.Request(url,data=data,method="POST")
with urllib.request.urlopen(req,timeout=30) as r:
    resp=json.loads(r.read())
    print("ok:",resp.get("ok"))

# גם צור prices.json ריק שהworkflow לא יקרס
import os; os.makedirs("output",exist_ok=True)
open("output/prices.json","w").write('{"updated":"demo","chains":{"tivtaam":{"name":"טיב טעם","store_id":"010","categories":{}},"keshet":{"name":"קשת","store_id":"015","categories":{}}}}')
