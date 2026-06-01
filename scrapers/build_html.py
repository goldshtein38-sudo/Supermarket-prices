"""
בונה קובץ HTML להשוואת מחירים מהנתונים שנאספו
"""

import json
import os
from datetime import datetime


def load_data():
    with open("output/prices.json", encoding="utf-8") as f:
        return json.load(f)


def format_price(item):
    """מחזיר מחיר מפורמט"""
    if item.get("is_weighted") and item.get("unit_price"):
        return f"₪{item['unit_price']}/100 גרם"
    elif item.get("price"):
        price = float(item["price"])
        if item.get("unit") and "ק" in item.get("unit", ""):
            return f"₪{price:.2f}/ק\"ג"
        return f"₪{price:.2f}"
    return "—"


def build_html(data):
    updated = data.get("updated", "")
    tiv = data["chains"].get("tivtaam", {})
    kes = data["chains"].get("keshet", {})
    
    tiv_cats = tiv.get("categories", {})
    kes_cats = kes.get("categories", {})
    
    cat_labels = {
        "עוף": ("🐓", "עוף טרי"),
        "הודו": ("🦃", "הודו"),
        "בקר": ("🥩", "בשר בקר"),
        "בשר לבן": ("🐖", "בשר לבן"),
        "פסטרמות": ("🍖", "פסטרמות"),
        "נקניקים": ("🌭", "נקניקים"),
        "נקניקיות": ("🌭", "נקניקיות"),
        "גבינות": ("🧀", "גבינות"),
    }

    # בנה טבלאות לכל קטגוריה
    tables_html = ""
    for cat_key, (emoji, cat_name) in cat_labels.items():
        tiv_items = tiv_cats.get(cat_key, [])
        kes_items = kes_cats.get(cat_key, [])
        
        if not tiv_items and not kes_items:
            continue

        # מיין לפי מחיר
        def sort_key(item):
            try:
                p = item.get("unit_price") or item.get("price") or "999"
                return float(p)
            except:
                return 999

        tiv_items = sorted(tiv_items, key=sort_key)
        kes_items = sorted(kes_items, key=sort_key)

        # בנה שורות
        rows = ""
        max_len = max(len(tiv_items), len(kes_items))
        for i in range(max_len):
            t = tiv_items[i] if i < len(tiv_items) else None
            k = kes_items[i] if i < len(kes_items) else None

            t_name = t["name"] if t else ""
            t_brand = t.get("manufacturer", "") if t else ""
            t_price = format_price(t) if t else ""

            k_name = k["name"] if k else ""
            k_brand = k.get("manufacturer", "") if k else ""
            k_price = format_price(k) if k else ""

            rows += f"""
            <tr>
              <td>
                <div class="pname">{t_name}</div>
                {'<div class="brand">' + t_brand + '</div>' if t_brand else ''}
              </td>
              <td class="price tiv">{t_price}</td>
              <td>
                <div class="pname">{k_name}</div>
                {'<div class="brand">' + k_brand + '</div>' if k_brand else ''}
              </td>
              <td class="price kes">{k_price}</td>
            </tr>"""

        tables_html += f"""
        <section class="cat-section" data-cat="{cat_key}">
          <div class="cat-header">
            <span class="emoji">{emoji}</span>
            <h2>{cat_name}</h2>
            <span class="counts">טיב טעם: {len(tiv_items)} | קשת: {len(kes_items)}</span>
          </div>
          <table class="compare-table">
            <thead>
              <tr>
                <th class="th-name">מוצר — טיב טעם</th>
                <th class="th-price tiv">מחיר</th>
                <th class="th-name">מוצר — קשת טעמים</th>
                <th class="th-price kes">מחיר</th>
              </tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
        </section>"""

    html = f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>השוואת מחירים — טיב טעם vs קשת טעמים</title>
<link href="https://fonts.googleapis.com/css2?family=Heebo:wght@400;600;700;900&display=swap" rel="stylesheet">
<style>
:root {{
  --tiv: #1a6b3c;
  --tiv-light: #d5f0e3;
  --kes: #1a5fa8;
  --kes-light: #dbeafe;
  --dark: #1a1a1a;
  --mid: #555;
  --border: #e0e0e0;
  --bg: #f7f7f5;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Heebo', sans-serif; background: var(--bg); color: var(--dark); }}

header {{
  background: linear-gradient(135deg, var(--tiv), #145a32 50%, var(--kes));
  color: white; padding: 20px 40px;
  display: flex; align-items: center; justify-content: space-between;
  position: sticky; top: 0; z-index: 100;
  box-shadow: 0 4px 16px rgba(0,0,0,.2);
}}
header h1 {{ font-size: 1.6rem; font-weight: 900; }}
header .sub {{ font-size: .8rem; opacity: .85; margin-top: 2px; }}
.badge {{ background: rgba(255,255,255,.2); border-radius: 8px; padding: 6px 14px; font-size: .82rem; font-weight: 600; }}

.controls {{
  background: white; padding: 14px 40px;
  display: flex; gap: 10px; flex-wrap: wrap;
  border-bottom: 2px solid var(--border);
  position: sticky; top: 72px; z-index: 99;
}}
.controls input {{
  flex: 1; min-width: 180px; padding: 8px 14px;
  border: 2px solid var(--border); border-radius: 8px;
  font-family: 'Heebo', sans-serif; font-size: .9rem;
}}
.controls input:focus {{ outline: none; border-color: var(--tiv); }}
.btn {{
  padding: 8px 14px; border: 2px solid var(--border); border-radius: 8px;
  background: white; font-family: 'Heebo', sans-serif; font-size: .84rem;
  cursor: pointer; white-space: nowrap; transition: all .18s;
}}
.btn:hover, .btn.active {{ background: var(--dark); color: white; border-color: var(--dark); }}

main {{ padding: 24px 40px; max-width: 1400px; margin: 0 auto; }}

.cat-section {{ margin-bottom: 44px; }}
.cat-header {{
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 14px; padding-bottom: 10px;
  border-bottom: 3px solid var(--dark);
}}
.cat-header .emoji {{ font-size: 1.8rem; }}
.cat-header h2 {{ font-size: 1.3rem; font-weight: 800; }}
.counts {{ margin-right: auto; font-size: .8rem; color: var(--mid); }}

.compare-table {{ width: 100%; border-collapse: collapse; font-size: .88rem; }}
.compare-table th {{
  padding: 9px 14px; text-align: right; font-weight: 700; font-size: .8rem;
  border-bottom: 2px solid var(--border);
}}
.th-name {{ width: 35%; }}
.th-price {{ width: 15%; }}
.th-price.tiv {{ background: var(--tiv-light); color: var(--tiv); }}
.th-price.kes {{ background: var(--kes-light); color: var(--kes); }}
.compare-table td {{
  padding: 8px 14px; border-bottom: 1px solid var(--border); vertical-align: middle;
}}
.compare-table tr:hover td {{ background: #f9f9f9; }}
.pname {{ font-weight: 600; line-height: 1.3; }}
.brand {{ font-size: .73rem; color: var(--mid); }}
.price {{ font-weight: 700; font-size: .95rem; }}
.price.tiv {{ color: var(--tiv); }}
.price.kes {{ color: var(--kes); }}

footer {{ text-align: center; padding: 24px; color: var(--mid); font-size: .8rem; border-top: 1px solid var(--border); background: white; margin-top: 32px; }}

@media(max-width:768px) {{
  header, main, .controls {{ padding-left: 12px; padding-right: 12px; }}
  header h1 {{ font-size: 1.2rem; }}
  .compare-table {{ font-size: .78rem; }}
  .compare-table td, .compare-table th {{ padding: 6px 8px; }}
}}
</style>
</head>
<body>

<header>
  <div>
    <h1>🔍 השוואת מחירים — טיב טעם vs קשת טעמים</h1>
    <div class="sub">נתונים ישירות מקבצי XML — מתעדכן אוטומטית כל שבוע</div>
  </div>
  <div class="badge">עודכן: {updated}</div>
</header>

<div class="controls">
  <input type="text" id="si" placeholder="🔍 חפש מוצר..." oninput="filter()">
  <button class="btn active" onclick="setCat(null,this)">הכל</button>
  <button class="btn" onclick="setCat('עוף',this)">🐓 עוף</button>
  <button class="btn" onclick="setCat('הודו',this)">🦃 הודו</button>
  <button class="btn" onclick="setCat('בקר',this)">🥩 בקר</button>
  <button class="btn" onclick="setCat('בשר לבן',this)">🐖 בשר לבן</button>
  <button class="btn" onclick="setCat('פסטרמות',this)">🍖 פסטרמות</button>
  <button class="btn" onclick="setCat('נקניקים',this)">🌭 נקניקים</button>
  <button class="btn" onclick="setCat('גבינות',this)">🧀 גבינות</button>
</div>

<main>{tables_html}</main>

<footer>נתונים מקובצי XML רשמיים — טיב טעם וקשת טעמים · עודכן: {updated}</footer>

<script>
let activeCat = null;
function filter() {{
  const q = document.getElementById('si').value.trim().toLowerCase();
  document.querySelectorAll('.cat-section').forEach(sec => {{
    const cat = sec.dataset.cat;
    if (activeCat && cat !== activeCat) {{ sec.style.display='none'; return; }}
    sec.style.display = '';
    sec.querySelectorAll('tbody tr').forEach(row => {{
      row.style.display = !q || row.textContent.toLowerCase().includes(q) ? '' : 'none';
    }});
  }});
}}
function setCat(cat, btn) {{
  activeCat = cat;
  document.querySelectorAll('.btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  filter();
}}
</script>
</body>
</html>"""

    return html


def main():
    os.makedirs("output", exist_ok=True)
    data = load_data()
    html = build_html(data)
    with open("output/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ Built output/index.html")


if __name__ == "__main__":
    main()
