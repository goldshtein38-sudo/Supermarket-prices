"""
בנאי HTML משופר להשוואת מחירים מהנתונים שנאספו
תוספות:
- Fuzzy matching בין מוצרים של שתי רשתות
- חישוב % הפרש מחיר
- דירוג לפי הזול ביותר
- כרטיס עדכון והערות
"""

import json
import os
from datetime import datetime
from difflib import SequenceMatcher

def load_data():
    with open("output/prices.json", encoding="utf-8") as f:
        return json.load(f)

def _to_float(v):
    try:
        return float(v)
    except (ValueError, TypeError):
        return None

def _unit_kind(item):
    """מזהה את בסיס היחידה: 'kg' למוצרי משקל, 'l' לנוזלים, None אחרת"""
    unit = (item.get("unit") or "").lower()
    if "ק" in unit and "ג" in unit:   # קילוגרם / ק"ג
        return "kg"
    if "100" in unit and "גר" in unit:  # 100 גרם
        return "100g"
    if "גרם" in unit or "גר" in unit:
        return "g"
    if "ליטר" in unit or 'ל"ל' in unit or "מ\"ל" in unit or "מל" in unit:
        return "l"
    return None

def price_per_kg(item):
    """
    מחזיר מחיר מנורמל לק"ג (או None אם אי אפשר לחשב הוגן).
    - מוצר שקיל: unit_price כבר ₪/ק"ג ברוב המקרים.
    - מוצר ארוז: price / (qty בק"ג).
    מחזיר (value, basis) כאשר basis הוא 'kg' או None.
    """
    price = _to_float(item.get("price"))
    up = _to_float(item.get("unit_price"))
    qty = _to_float(item.get("qty"))
    kind = _unit_kind(item)

    # מוצר שקיל - unit_price הוא המחיר ליחידת המידה
    if item.get("is_weighted") and up and up > 0:
        if kind == "kg":
            return (up, "kg")
        if kind == "100g":
            return (up * 10, "kg")     # ₪/100גרם -> ₪/ק"ג
        # ברירת מחדל לשקיל: ההנחה היא ק"ג
        return (up, "kg")

    # מוצר ארוז - חשב מהמחיר והכמות
    if price and price > 0 and qty and qty > 0:
        if kind in ("g", "100g"):      # qty בגרמים
            return (price / qty * 1000, "kg")
        if kind == "kg":               # qty בק"ג
            return (price / qty, "kg")
        if kind == "l":                # qty בליטר -> נשווה ל"ליטר" בנפרד
            return (price / qty, "l")
    # אם יש unit_price ארוז (מחושב ל-100 גרם בד"כ)
    if up and up > 0 and kind == "100g":
        return (up * 10, "kg")
    return (None, None)

def format_price_display(item):
    """תצוגת מחיר מנורמל לק"ג (כל המוצרים שקילים = מעדנייה/קצבייה)"""
    pk, basis = price_per_kg(item)
    if pk and basis == "kg":
        return f"₪{pk:.1f} לק\"ג"
    if pk and basis == "l":
        return f"₪{pk:.1f} לליטר"
    price = _to_float(item.get("price"))
    if price:
        return f"₪{price:.2f}"
    return "—"

import re as _re

_STOP = {"במשקל","טרי","טרייה","טריה","ארוז","ארוזה","גרם","גר","קג","ק","מ","ל","יח","יחידה",
         "לא","ידוע","עם","ללא","ב","של","אחוז","שומן",
         # מילות אריזה/יחידה/שיווק נטרליות (לא מבדילות מוצר)
         "מניה","מזרע","יח'","ליחידה","לק","בלוק","גוש","חבילה","מארז","אריזה","ואקום","בוואקום",
         "מובחר","מעודן","מעודנת","פרימיום","איכות","איכותי","משובח","ביתי","ביתית","רגיל","רגילה",
         "חדש","חדשה","מבצע","משק","קטן","גדול","חצי"}

def _normalize(s):
    """מסיר מספרים, יחידות, מילות עצירה - משאיר מילות תוכן"""
    s = s.lower()
    s = _re.sub(r'[0-9]+', ' ', s)              # הסר מספרים
    s = _re.sub(r'[^\u0590-\u05ff ]', ' ', s)   # רק עברית ורווחים
    words = [w for w in s.split() if w and w not in _STOP and len(w) > 1]
    # נרמול נטיות/כתיב: אחד וריאנטים נפוצים כדי לתפוס התאמות אמת
    norm = []
    for w in words:
        w = w.replace("סקייה", "סקיה").replace("צקייה", "סקיה")  # רוסית
        if w.endswith("ית") and len(w) > 4:   # פיקנטית -> פיקנטי
            w = w[:-1]
        elif w.endswith("ים") and len(w) > 4:  # רבים -> יחיד
            w = w[:-2]
        elif w.endswith("ות") and len(w) > 4:  # רבים נקבה
            w = w[:-2]
        elif w.endswith("ת") and len(w) > 4 and w not in ("פסטרמת","גבינת"):  # מעושנת->מעושן
            w = w[:-1]
        norm.append(w)
    return norm

def similarity(a, b):
    """דמיון מבוסס מילות תוכן משותפות + רצף תווים"""
    wa, wb = _normalize(a), _normalize(b)
    if not wa or not wb:
        return 0.0
    sa, sb = set(wa), set(wb)
    # Jaccard על מילים
    inter = sa & sb
    union = sa | sb
    jaccard = len(inter) / len(union) if union else 0
    # דרוש לפחות מילת תוכן אחת משותפת משמעותית
    if not inter:
        return 0.0
    # שילוב: jaccard + דמיון רצף
    seq = SequenceMatcher(None, " ".join(wa), " ".join(wb)).ratio()
    return 0.6 * jaccard + 0.4 * seq

# מאפיינים שחייבים להתאים בין שני מוצרים כדי שהם יהיו "אותה סחורה".
# כל קבוצה = מאפיין בינארי. אם מוצר אחד מכיל מילה מהקבוצה והשני לא -> לא תואמים.
ATTRIBUTE_GROUPS = [
    ["מעושן", "מעושנת", "מעושנים", "מעושנות", "עישון"],   # עישון
    ["מטוגן", "מטוגנת", "מטוגנים", "מטוגנות", "טיגון"],    # טיגון
    ["מבושל", "מבושלת", "מבושלים", "בישול", "על האש", "בגריל", "צלוי", "צלויה", "אפוי", "אפויה"],  # בישול/צלייה
    ["ממולא", "ממולאת", "ממולאים", "במילוי"],            # מילוי
    ["טחון", "טחונה", "טחונים"],                          # טחון
    ["פרוס", "פרוסה", "פרוסות", "פרוסים", "פרוס דק"],     # פרוס
    ["שלם", "שלמה", "שלמים"],                             # שלם
    ["עם בצל", "ברוטב", "ברנדי", "פיקנטי", "חריף", "מתובל", "בתיבול", "מתוק"],  # תוספות/תיבול
    ["דל שומן", "ללא שומן", "לייט", "דיאט"],              # דל שומן
]

def _attr_set(name):
    """מחזיר אילו מאפיינים (אינדקס קבוצה) קיימים בשם"""
    s = set()
    for i, grp in enumerate(ATTRIBUTE_GROUPS):
        for kw in grp:
            if kw in name:
                s.add(i)
                break
    # מאפיין עצם: 'בלי עצם'/'ללא עצם' מול 'עם עצם' - הבדל מהותי
    if "בלי עצם" in name or "ללא עצם" in name or "נקי" in name:
        s.add("boneless")
    elif "עם עצם" in name:
        s.add("bone-in")
    return s

def attributes_compatible(a, b):
    """
    שני מוצרים תואמים רק אם יש להם בדיוק אותם מאפייני עיבוד/צורה.
    אם לאחד יש 'מעושן' ולשני אין -> לא תואם (סחורה שונה).
    """
    return _attr_set(a) == _attr_set(b)

# מילים ניטרליות בלבד - לא משפיעות על זהות המוצר או מחירו (אריזה/מצב/יחידה).
# מילים כמו 'דק','פרימיום','איטלקי' אינן כאן - הן מבדילות מוצר ומחיר.
_GENERIC = {
    "טרי","טרייה","טריה","במשקל","ארוז","ארוזה","שקיל","מניה","מארז","חבילה",
    "גוש","בלוק","חדש","חדשה","מפורק","נקי","יח","יחידה",
}

def core_words_match(a, b):
    """
    בודק שמילות הליבה (אחרי הסרת גנריות) זהות בעיקרן.
    מונע 'לקס עגל'↔'לב עגל' (לקס≠לב) או 'נקניק ליברניה'↔'נקניק לבירה'.
    דורש: אין לאף צד מילת-ליבה ייחודית משמעותית שהשני חסר.
    """
    ca = set(w for w in _normalize(a) if w not in _GENERIC)
    cb = set(w for w in _normalize(b) if w not in _GENERIC)
    if not ca or not cb:
        return False
    only_a = ca - cb
    only_b = cb - ca
    shared = ca & cb
    # חייבת להיות לפחות מילת ליבה משותפת אחת
    if not shared:
        return False
    # אסור שלאחד הצדדים תהיה מילת ליבה ייחודית (נתח/סוג שונה)
    # מותר הבדל אם המילה הייחודית היא תת-מחרוזת של מילה משותפת (נטייה)
    def is_substring_of_shared(words, sh):
        return all(any(w in s or s in w for s in sh) for w in words)
    if only_a and not is_substring_of_shared(only_a, shared):
        return False
    if only_b and not is_substring_of_shared(only_b, shared):
        return False
    return True

def fuzzy_match(tiv_items, kes_items, threshold=0.5):
    """
    יוצר זוגות של מוצרים דומים בין שתי רשתות.
    מתאים רק מוצרים עם אותם מאפייני עיבוד (טרי/מעושן/מטוגן/פרוס/שלם וכו').
    """
    matched_pairs = []
    used_kes_indices = set()
    unmatched_tiv = []

    for tiv in tiv_items:
        best_match = None
        best_score = threshold
        best_idx = -1

        for idx, kes in enumerate(kes_items):
            if idx in used_kes_indices:
                continue
            # שער ראשון: מאפייני עיבוד חייבים להיות זהים
            if not attributes_compatible(tiv["name"], kes["name"]):
                continue
            # שער שני: מילות הליבה (נתח/סוג) חייבות להתאים
            if not core_words_match(tiv["name"], kes["name"]):
                continue
            score = similarity(tiv["name"], kes["name"])
            if score > best_score:
                best_score = score
                best_match = kes
                best_idx = idx

        if best_match:
            matched_pairs.append((tiv, best_match))
            used_kes_indices.add(best_idx)
        else:
            unmatched_tiv.append(tiv)

    unmatched_kes = [kes for idx, kes in enumerate(kes_items) if idx not in used_kes_indices]

    return {
        "matched_pairs": matched_pairs,
        "unmatched_tiv": unmatched_tiv,
        "unmatched_kes": unmatched_kes,
    }

def compare_prices(tiv_item, kes_item):
    """
    משווה על בסיס מחיר מנורמל לק"ג (או ליטר).
    מחזיר: (cheaper, diff_percent, tiv_pk, kes_pk, comparable)
    comparable=False כשאי אפשר להשוות הוגן (בסיס שונה / חסר נתון).
    """
    tpk, tb = price_per_kg(tiv_item)
    kpk, kb = price_per_kg(kes_item)
    if tpk is None or kpk is None or tb != kb:
        return (None, None, tpk, kpk, False)
    diff = abs(tpk - kpk) / max(tpk, kpk) * 100
    cheaper = "tiv" if tpk < kpk else "kes"
    return (cheaper, diff, tpk, kpk, True)

def _brand(item):
    m = (item.get("manufacturer") or "").strip()
    if not m or m in ("לא ידוע", "לא  ידוע", "unknown", "UNKNOWN"):
        return ""
    return f'<div class="brand">{m}</div>'

def build_matched_section(cat_key, cat_name, emoji, match_data):
    """בונה קטע השוואה ישירה של מוצרים תואמים"""
    matched = match_data["matched_pairs"]
    unmatched_tiv = match_data["unmatched_tiv"]
    unmatched_kes = match_data["unmatched_kes"]
    
    if not matched and not unmatched_tiv and not unmatched_kes:
        return ""
    
    rows = ""
    
    # 1. מוצרים תואמים (ממוינים לפי הפרש מחיר)
    matched_with_diff = []
    for tiv, kes in matched:
        cheaper, diff, tp, kp, comparable = compare_prices(tiv, kes)
        matched_with_diff.append({
            "tiv": tiv, "kes": kes, "cheaper": cheaper,
            "diff": diff, "comparable": comparable,
        })

    # מיין: קודם ברי-השוואה לפי הפרש גדול, אחר כך הלא-ברי-השוואה
    matched_with_diff.sort(key=lambda x: (x["comparable"], x["diff"] or 0), reverse=True)

    for pair in matched_with_diff:
        tiv, kes = pair["tiv"], pair["kes"]
        cheaper = pair["cheaper"]
        diff = pair["diff"]
        comparable = pair["comparable"]

        tiv_display = format_price_display(tiv)
        kes_display = format_price_display(kes)

        # הדגשה רק כשההשוואה הוגנת
        if comparable and cheaper == "tiv":
            tiv_style = 'style="background: #d5f0e3; font-weight: 700;"'
            kes_style = ''
        elif comparable and cheaper == "kes":
            kes_style = 'style="background: #dbeafe; font-weight: 700;"'
            tiv_style = ''
        else:
            tiv_style = kes_style = ''

        if comparable and diff is not None:
            diff_text = ""
        else:
            diff_text = "<small style='color:#999'>(בסיס שונה)</small>"

        rows += f"""
<tr class="matched-row">
    <td class="col-name">
        <div class="pname">{tiv['name']}</div>
        {_brand(tiv)}
    </td>
    <td class="col-price" {tiv_style}>{tiv_display}</td>
    <td class="col-name">
        <div class="pname">{kes['name']}</div>
        {_brand(kes)}
    </td>
    <td class="col-price" {kes_style}>{kes_display} {diff_text}</td>
</tr>"""
    
    # 2. מוצרים שלא נמצאה להם התאמה
    if unmatched_tiv or unmatched_kes:
        rows += '<tr class="separator-row"><td colspan="4"><strong>מוצרים ללא התאמה</strong></td></tr>'
        
        for item in unmatched_tiv:
            rows += f"""
<tr class="unmatched-row">
    <td class="col-name" style="background: #f0f0f0;">
        <div class="pname">{item['name']}</div>
        {_brand(item)}
    </td>
    <td class="col-price" style="background: #f0f0f0;">{format_price_display(item)}</td>
    <td colspan="2" style="text-align: center; color: #999; font-size: 0.85rem;">אין במקביל בקשת</td>
</tr>"""
        
        for item in unmatched_kes:
            rows += f"""
<tr class="unmatched-row">
    <td colspan="2" style="text-align: center; color: #999; font-size: 0.85rem;">אין במקביל בטיב טעם</td>
    <td class="col-name" style="background: #f0f0f0;">
        <div class="pname">{item['name']}</div>
        {_brand(item)}
    </td>
    <td class="col-price" style="background: #f0f0f0;">{format_price_display(item)}</td>
</tr>"""
    
    total_items = len(matched) + len(unmatched_tiv) + len(unmatched_kes)
    
    return f"""
<section class="cat-section" data-cat="{cat_key}">
    <div class="cat-header">
        <span class="emoji">{emoji}</span>
        <h2>{cat_name}</h2>
        <span class="counts">{len(matched)} זוגות | {len(unmatched_tiv)} בטיב בלבד | {len(unmatched_kes)} בקשת בלבד</span>
    </div>
    <table class="compare-table">
        <thead>
            <tr>
                <th class="th-name">מוצר — טיב טעם</th>
                <th class="th-price tiv">💰 מחיר</th>
                <th class="th-name">מוצר — קשת טעמים</th>
                <th class="th-price kes">💰 מחיר</th>
            </tr>
        </thead>
        <tbody>{rows}</tbody>
    </table>
</section>"""

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
    
    tables_html = ""
    for cat_key, (emoji, cat_name) in cat_labels.items():
        tiv_items = tiv_cats.get(cat_key, [])
        kes_items = kes_cats.get(cat_key, [])
        
        if not tiv_items and not kes_items:
            continue
        
        # עשה fuzzy match
        match_data = fuzzy_match(tiv_items, kes_items, threshold=0.5)
        
        section = build_matched_section(cat_key, cat_name, emoji, match_data)
        if section:
            tables_html += section
    
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
        body {{ font-family: 'Heebo', sans-serif; background: var(--bg); color: var(--dark); line-height: 1.6; }}
        
        /* Header */
        header {{
            background: linear-gradient(135deg, var(--tiv), #145a32 50%, var(--kes));
            color: white;
            padding: 20px 40px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: 0 4px 16px rgba(0,0,0,.2);
        }}
        header h1 {{ font-size: 1.6rem; font-weight: 900; }}
        header .sub {{ font-size: .8rem; opacity: .85; margin-top: 2px; }}
        .badge {{ background: rgba(255,255,255,.2); border-radius: 8px; padding: 6px 14px; font-size: .82rem; font-weight: 600; }}
        
        /* Controls */
        .controls {{
            background: white;
            padding: 14px 40px;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            border-bottom: 2px solid var(--border);
            position: sticky;
            top: 72px;
            z-index: 99;
        }}
        .controls input {{
            flex: 1;
            min-width: 180px;
            padding: 8px 14px;
            border: 2px solid var(--border);
            border-radius: 8px;
            font-family: 'Heebo', sans-serif;
            font-size: .9rem;
        }}
        .controls input:focus {{ outline: none; border-color: var(--tiv); }}
        
        .btn {{
            padding: 8px 14px;
            border: 2px solid var(--border);
            border-radius: 8px;
            background: white;
            font-family: 'Heebo', sans-serif;
            font-size: .84rem;
            cursor: pointer;
            white-space: nowrap;
            transition: all .18s;
        }}
        .btn:hover, .btn.active {{ background: var(--dark); color: white; border-color: var(--dark); }}
        
        /* Main */
        main {{ padding: 24px 40px; max-width: 1400px; margin: 0 auto; }}
        
        .cat-section {{ margin-bottom: 44px; }}
        .cat-header {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 14px;
            padding-bottom: 10px;
            border-bottom: 3px solid var(--dark);
        }}
        .cat-header .emoji {{ font-size: 1.8rem; }}
        .cat-header h2 {{ font-size: 1.3rem; font-weight: 800; }}
        .counts {{ margin-right: auto; font-size: .8rem; color: var(--mid); }}
        
        /* Table */
        .compare-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: .88rem;
            background: white;
            box-shadow: 0 1px 4px rgba(0,0,0,.05);
        }}
        
        .compare-table th {{
            padding: 9px 14px;
            text-align: right;
            font-weight: 700;
            font-size: .8rem;
            border-bottom: 2px solid var(--border);
        }}
        
        .th-name {{ width: 35%; }}
        .th-price {{ width: 15%; }}
        .th-price.tiv {{ background: var(--tiv-light); color: var(--tiv); }}
        .th-price.kes {{ background: var(--kes-light); color: var(--kes); }}
        
        .compare-table td {{
            padding: 8px 14px;
            border-bottom: 1px solid var(--border);
            vertical-align: top;
        }}
        
        .compare-table tr:hover td {{ background: #fafaf8; }}
        
        .col-name {{ width: 35%; }}
        .col-price {{ width: 15%; text-align: center; }}
        
        .pname {{ font-weight: 600; line-height: 1.4; }}
        .brand {{ font-size: .73rem; color: var(--mid); margin-top: 2px; }}
        
        .compare-table .price {{
            font-weight: 700;
            font-size: .98rem;
        }}
        
        /* Highlighted rows */
        .matched-row {{ }}
        .unmatched-row {{ opacity: 0.75; }}
        .separator-row td {{
            padding: 12px 14px;
            background: #f0f0f0;
            font-weight: 600;
            font-size: .85rem;
            color: var(--mid);
            border-top: 2px solid var(--border);
        }}
        
        /* Footer */
        footer {{
            text-align: center;
            padding: 24px;
            color: var(--mid);
            font-size: .8rem;
            border-top: 1px solid var(--border);
            background: white;
            margin-top: 32px;
        }}
        
        /* Responsive */
        @media(max-width:768px) {{
            header, main, .controls {{ padding-left: 12px; padding-right: 12px; }}
            header h1 {{ font-size: 1.2rem; }}
            .compare-table {{ font-size: .78rem; }}
            .compare-table td, .compare-table th {{ padding: 6px 8px; }}
            .cat-header {{ flex-direction: column; align-items: flex-start; }}
            .counts {{ margin-right: 0; margin-top: 6px; }}
        }}
    </style>
</head>
<body>

<header>
    <div>
        <h1>🔍 השוואת מחירים — טיב טעם vs קשת טעמים</h1>
        <div class="sub">השוואה חכמה עם זיהוי מוצרים אוטומטי • נתונים מקבצי XML רשמיים</div>
    </div>
    <div class="badge">✅ עודכן: {updated}</div>
</header>

<div class="controls">
    <input type="text" id="si" placeholder="🔍 חפש מוצר או יצרן..." oninput="filter()">
    <button class="btn active" onclick="setCat(null,this)">📊 הכל</button>
    <button class="btn" onclick="setCat('עוף',this)">🐓 עוף</button>
    <button class="btn" onclick="setCat('הודו',this)">🦃 הודו</button>
    <button class="btn" onclick="setCat('בקר',this)">🥩 בקר</button>
    <button class="btn" onclick="setCat('בשר לבן',this)">🐖 בשר לבן</button>
    <button class="btn" onclick="setCat('פסטרמות',this)">🍖 פסטרמות</button>
    <button class="btn" onclick="setCat('נקניקים',this)">🌭 נקניקים</button>
    <button class="btn" onclick="setCat('גבינות',this)">🧀 גבינות</button>
</div>

<main>{tables_html}</main>

<footer>
    📊 נתונים מקבצי PriceFull רשמיים (חוק המזון 2014) • טיב טעם וקשת טעמים • עודכן: {updated}<br>
    💡 המוצרים המוצגים זוהו אוטומטית לפי דמיון שם • אם חסרה התאמה, נא לדווח
</footer>

<script>
let activeCat = null;

function filter() {{
    const q = document.getElementById('si').value.trim().toLowerCase();
    document.querySelectorAll('.cat-section').forEach(sec => {{
        const cat = sec.dataset.cat;
        if (activeCat && cat !== activeCat) {{ 
            sec.style.display='none'; 
            return; 
        }}
        
        let hasVisible = false;
        sec.querySelectorAll('tbody tr').forEach(row => {{
            // דלג על שורות מחלק / כותרת
            if (row.classList.contains('separator-row')) {{
                row.style.display = '';
                return;
            }}
            
            const visible = !q || row.textContent.toLowerCase().includes(q);
            row.style.display = visible ? '' : 'none';
            if (visible) hasVisible = true;
        }});
        
        sec.style.display = hasVisible ? '' : 'none';
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
    print("✅ Built output/index.html with fuzzy matching and price comparisons")

if __name__ == "__main__":
    main()
