"""
scrape.py — סניף כרמיאל (טיב 010, קשת 015), קטגוריזציה מדויקת
גישה: HTTPS portal. סינון לפי whitelist מוקפד + blacklist רעש.
"""
import os, json, gzip, re, traceback
import requests, urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import xml.etree.ElementTree as ET
from datetime import datetime

BASE = "https://url.publishedprices.co.il"
CHAINS = {
    "tivtaam": {"name":"טיב טעם","user":"TivTaam","password":"","chain_id":"7290873255550","store":"010"},
    "keshet":  {"name":"קשת טעמים","user":"Keshet","password":"","chain_id":"7290785400000","store":"015"},
}

# blacklist - מוצרים שנפסלים לחלוטין (מזון לחיות, חטיפים, מרקים, אוכל מוכן ארוז, דגים)
BLACKLIST = [
    "לכלב","לחתול","לגור","לגורים","חתול","כלב","גורי","מזון יבש","מזון לח","פריסקיז","פנסי","פיין קט",
    "סימבה","פרמיו","נייטיב","דוג","קט ","ציפס","צ'יפס","שבבי","חטיף","קליק","במבה","ביסלי",
    "מרק","אטריות","ראמן","נודלס","אבקת","ציר ","קוביות ציר","תבלין","תיבול","תערובת תיבול",
    "רוטב","קטשופ","מיונז","ממרח","ממורח","פסטה ","אורז ","קמח","שמן","חומץ",
    "לזניה","תבשיל","קציצות","לביבות","סלט","תסלט","פיצה","בורקס","פאי","מאפה","סנדוויץ",
    "קפוא","קפואה","להכנה","מוכן","משקה","תה ","קפה","סוכר","דבש","ריבה","שוקולד","ופל","עוגי","עוגה",
    "גלידה","שלגון","יוגורט","מעדן","פודינג","שמנת חמוצה","חלב ","משקאות",
    "לולו",  # מותג עוף - לפי בקשת המשתמש
    # דגים - לא בקטגוריות המעדנייה/קצבייה שביקש המשתמש
    "סלמון","סולומון","סלומון","דג ","דגים","הרינג","מקרל","טונה","פילה דג","בקלה","פורל","דניס","אמנון","בורי","לברק","טרוטה","סרדין","בליק",
]

# מילות מפתח לכל קטגוריה. הסדר חשוב: קטגוריה ספציפית לפני כללית.
# כל קטגוריה: (must_have_any, must_not_have_any)
CATEGORY_RULES = [
    ("הודו", {
        "any": ["הודו","קוטלט הודו","שוק הודו","שווארמה הודו"],
        "not": [],
    }),
    ("בקר", {
        "any": ["בקר","עגל","אנטריקוט","אסאדו","אנטרקוט","סינטה","פיקניה","שייטל","פילה בקר",
                "אונטריב","צלי בקר","כתף בקר","חזה בקר","לשון בקר","אוסבוקו","שריר בקר","ריב איי",
                "אצבעות בקר","דנ ver","אצ'ילי","אסאדו","שפיץ צ'אך","צ'אך","אוכף","ראמשטיין","פילה מדומה",
                "שפונדרה"],
        "not": ["הודו","עוף","חזיר"],
    }),
    ("פסטרמות", {
        "any": ["פסטרמה","פסטירמה","קורנביף","רוסטביף","בייקון","בקון","שינקן","שינקה",
                "קסטיצה","קוסטיצה","בריסקט","קוטלט שינקן","קוטלט מעושן"],
        "not": [],
    }),
    ("נקניקיות", {
        "any": ["נקניקיות","נקניקיית","וינר","פרנקפורטר","הוט דוג","מרגז","קבנוס"],
        "not": [],
    }),
    ("נקניקים", {
        "any": ["נקניק","סלמי","מורטדלה","סרוולד","אודסקיה","פפרוני","צ'וריזו","פריזר",
                "דבריצ'ין","פלמידה","דוקטורסקי","קיץ שלם","פרלמנט"],
        "not": [],
    }),
    ("בשר לבן", {
        "any": ["חזיר","חזירון","שפק","אמסטרדם","פרושוטו","קרקוב","קרקובסקי","קרקובסקיה",
                "בוזנינה","כתף לבן","צוואר לבן","בטן לבן","שומן לבן","קותלי","קסלר","פטיט",
                "קוטלט לבן","פנצ'טה","פולקה","ריב לבן","נתח לבן","לונדה"],
        "not": ["בקר","הודו","עוף","פסטרמה","נקניק","סלמי","גבינה","גבינת"],
    }),
    ("עוף", {
        "any": ["עוף","פרגית","שניצל עוף","חזה עוף","שוקיים","ירכיים","כרעיים","כנפיים","כנף",
                "כבד עוף","לב עוף","לבבות","גב עוף","שווארמה עוף","נתחי עוף","טחון עוף","קורקבן"],
        "not": ["הודו","בקר","חזיר"],
    }),
    ("גבינות", {
        "any": ["גבינה","גבינת","קממבר","קממברט","מוצרלה","פרמזן","גאודה","בולגרית","ריקוטה",
                "רוקפור","צ'דר","אמנטל","פטה","חלומי","מסקרפונה","טבורוג","קוטג","גבינו",
                "ברינזה","פרובולון","מנצ'גו","גורגונזולה","בריא","חצילים בגבינה","שמנת לבישול"],
        "not": ["תחליף"],
    }),
]

CAT_NAMES = [c for c,_ in CATEGORY_RULES]

def categorize(name):
    n = name.strip()
    low = n.lower()
    for b in BLACKLIST:
        if b in low:
            return None
    for cat, rule in CATEGORY_RULES:
        # חייב להכיל לפחות מילה אחת מ-any
        if not any(kw in n for kw in rule["any"]):
            continue
        # ואסור שיכיל מילה מ-not
        if any(bad in n for bad in rule["not"]):
            continue
        return cat
    return None

LOG=[]
def log(s): LOG.append(str(s)); print(s)

def find_token(html):
    for p in [r'name=["\']csrftoken["\']\s+value=["\']([^"\']+)',
              r'<meta\s+name=["\']csrftoken["\']\s+content=["\']([^"\']+)']:
        m=re.search(p,html,re.I)
        if m: return m.group(1)
    return None

def login(s,u,p):
    r=s.get(f"{BASE}/login",timeout=30); t=find_token(r.text)
    pl={"username":u,"password":p,"Submit":"Sign in"}
    if t: pl["csrftoken"]=t
    s.post(f"{BASE}/login/user",data=pl,timeout=30,headers={"Referer":f"{BASE}/login"})
    chk=s.get(f"{BASE}/file",timeout=30); return find_token(chk.text) or t

def list_files(s,t):
    d={"sEcho":"1","iColumns":"5","sColumns":",,,,","iDisplayStart":"0","iDisplayLength":"100000","mDataProp_0":"fname","sSearch":"","cd":"/"}
    if t: d["csrftoken"]=t
    r=s.post(f"{BASE}/file/json/dir",timeout=60,data=d,headers={"Referer":f"{BASE}/file","X-CSRFToken":t or "","X-Requested-With":"XMLHttpRequest"})
    return [row.get("fname","") for row in r.json().get("aaData",[])]

def pick(files,chain,store):
    c=[f for f in files if "PriceFull" in f and chain in f and any(seg==store or seg.lstrip("0")==store.lstrip("0") for seg in f.replace(".gz","").split("-")[1:])]
    return sorted(c)[-1] if c else None

def process_chain(key,cfg):
    categorized={c:[] for c in CAT_NAMES}
    store_label=cfg["store"]
    log(f"\n{'='*60}\n{cfg['name']} store={cfg['store']}")
    s=requests.Session(); s.verify=False; s.headers.update({"User-Agent":"Mozilla/5.0"})
    try:
        t=login(s,cfg["user"],cfg["password"])
        files=list_files(s,t)
        tgt=pick(files,cfg["chain_id"],cfg["store"])
        if not tgt:
            log("  no file"); return categorized,store_label
        log(f"  Using: {tgt}")
        raw=s.get(f"{BASE}/file/d/{tgt}",timeout=120).content
        try: content=gzip.decompress(raw)
        except: content=raw
        try: root=ET.fromstring(content)
        except: root=ET.fromstring(content.decode("utf-8-sig",errors="ignore"))
        sid=root.find(".//StoreID")
        if sid is not None and (sid.text or "").strip(): store_label=sid.text.strip()
        items=root.findall(".//Item")
        cnt=0
        for it in items:
            name=(it.findtext("ItemName") or "").strip()
            price=it.findtext("ItemPrice") or ""
            status=it.findtext("ItemStatus") or "1"
            if not (name and price) or status=="0": continue
            try:
                if float(price)<=0: continue
            except: continue
            # רק מוצרים שקילים = מעדנייה/קצבייה (לא ארוז/מקפיא)
            is_weighted = (it.findtext("bIsWeighted") or "0") == "1"
            if not is_weighted:
                continue
            cat=categorize(name)
            if cat:
                categorized[cat].append({
                    "name":name,
                    "manufacturer":it.findtext("ManufactureName") or "",
                    "item_code":it.findtext("ItemCode") or "",
                    "price":price,
                    "unit_price":it.findtext("UnitOfMeasurePrice") or "",
                    "unit":it.findtext("UnitOfMeasure") or it.findtext("UnitQty") or "",
                    "is_weighted": True,
                    "qty":it.findtext("Quantity") or "",
                })
                cnt+=1
        log(f"  Total: {len(items)} | Categorized: {cnt}")
        for c,lst in categorized.items():
            if lst: log(f"      {c}: {len(lst)}")
    except Exception as e:
        log(f"  ERROR: {e}\n{traceback.format_exc()}")
    finally:
        s.close()
    return categorized,store_label

def main():
    os.makedirs("output",exist_ok=True)
    result={"updated":datetime.now().strftime("%d.%m.%Y %H:%M"),"note":"נתונים מסניף כרמיאל",
            "stores":{"tivtaam":"010","keshet":"015"},"chains":{}}
    try:
        for key,cfg in CHAINS.items():
            cats,store=process_chain(key,cfg)
            result["chains"][key]={"name":cfg["name"],"store_id":store,"categories":cats}
    finally:
        with open("output/prices.json","w",encoding="utf-8") as f:
            json.dump(result,f,ensure_ascii=False,indent=2)
        with open("output/diagnose_output.txt","w",encoding="utf-8") as f:
            f.write("\n".join(LOG))
        print("✅ done")

if __name__=="__main__": main()
