# 🔍 השוואת מחירים — טיב טעם vs קשת טעמים

כלי להשוואת מחירי מעדנייה, בשר, נקניקים וגבינות בין טיב טעם וקשת טעמים.

## איך זה עובד

- הנתונים מגיעים ישירות מקבצי XML שהרשתות מחויבות לפרסם לפי חוק המזון 2014
- GitHub Actions מריץ את הסקריפט אוטומטית כל יום שני בבוקר
- מתעדכן ב-Netlify ומפורסם אוטומטית

## מבנה הפרויקט

```
scrapers/
  scrape.py       # מוריד XML ומנתח מחירים
  build_html.py   # בונה קובץ HTML להשוואה
output/
  prices.json     # נתוני מחירים מעובדים
  index.html      # דף ההשוואה
.github/workflows/
  weekly-update.yml  # הרצה אוטומטית שבועית
```

## הגדרת Secrets ב-GitHub

דרוש להוסיף שני Secrets תחת Settings → Secrets → Actions:

- `NETLIFY_AUTH_TOKEN` — טוקן מ-Netlify
- `NETLIFY_SITE_ID` — ה-Site ID מ-Netlify

## הרצה ידנית

```bash
python scrapers/scrape.py
python scrapers/build_html.py
```
