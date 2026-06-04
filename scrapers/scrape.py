"""אבחון: מוצרי בשר לבן + מוצרים שקילים שלא סווגו כלל"""
import os, gzip, re
import requests, urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import xml.etree.ElementTree as ET

BASE="https://url.publishedprices.co.il"
def ftok(h):
    m=re.search(r'name=["\']csrftoken["\']\s+value=["\']([^"\']+)',h,re.I)
    return m.group(1) if m else None
def login(s,u):
    r=s.get(f"{BASE}/login",timeout=30);t=ftok(r.text)
    pl={"username":u,"password":"","Submit":"Sign in"}
    if t: pl["csrftoken"]=t
    s.post(f"{BASE}/login/user",data=pl,timeout=30,headers={"Referer":f"{BASE}/login"})
    return ftok(s.get(f"{BASE}/file",timeout=30).text) or t
def lst(s,t):
    d={"sEcho":"1","iColumns":"5","sColumns":",,,,","iDisplayLength":"100000","mDataProp_0":"fname","cd":"/"}
    if t: d["csrftoken"]=t
    r=s.post(f"{BASE}/file/json/dir",timeout=60,data=d,headers={"Referer":f"{BASE}/file","X-CSRFToken":t or "","X-Requested-With":"XMLHttpRequest"})
    return [x.get("fname","") for x in r.json().get("aaData",[])]

# whitelist הנוכחי
CATEGORIES = {
    "עוף":["עוף טרי","עוף שלם","חזה עוף","שוקיים","ירכיים","כרעיים","כנפיים עוף","כנף עוף","פרגית","שניצל עוף","טחון עוף","כבד עוף טרי","לבבות עוף","גב עוף","שווארמה עוף","נתחי עוף"],
    "הודו":["הודו טרי","חזה הודו","שניצל הודו","טחון הודו","שוקי הודו","כנפי הודו","נקניק הודו","שווארמה הודו"],
    "בקר":["בקר טרי","אנטריקוט","אסאדו","צלעות בקר","סטייק","שייטל","פילה בקר","סינטה","אונטריב","טחון בקר","בשר טחון","צלי בקר","כתף בקר","חזה בקר","לשון בקר","אוסבוקו","פילה מדומה","שריר בקר","ריב איי"],
    "בשר לבן":["נתח חזיר","חזיר טרי","פילה חזיר","צוואר חזיר","שניצל חזיר","קוטלט"],
    "פסטרמות":["פסטרמה","פסטירמה","קורנביף","רוסטביף","בייקון","שינקן","שינקה","קסטיצה","קוסטיצה","בריסקט"],
    "נקניקים":["נקניק","סלמי","קבנוס","מורטדלה","סרוולד","אודסקיה","פפרוני","צ'וריזו","פריזר","דבריצ'ין","פלמידה"],
    "נקניקיות":["נקניקיות","נקניקיית","וינר","פרנקפורטר","הוט דוג","מרגז"],
    "גבינות":["גבינה","גבינת","קממבר","קממברט","מוצרלה","פרמזן","גאודה","בולגרית","ריקוטה","ברי ","רוקפור","צ'דר","אמנטל","פטה","חלומי","מסקרפונה","טבורוג","קוטג","שמנת לבישול","גבינו"],
}
BLACKLIST=["לכלב","לחתול","לגור","חתול","כלב","מזון יבש","מזון לח","פריסקיז","פנסי","פיין קט","סימבה","פרמיו","נייטיב","ציפס","שבבי","חטיף","מרק","אטריות","ראמן","נודלס","אבקת","ציר ","קוביות ציר","תבלין","תיבול","רוטב","קטשופ","מיונז","ממרח","פסטה ","אורז ","קמח","שמן","חומץ","לזניה","תבשיל","קציצות","לביבות","סלט","תסלט","פיצה","בורקס","פאי","מאפה","קפוא","להכנה","מוכן","משקה","סוכר","דבש","ריבה","שוקולד","ופל","עוגי","עוגה","גלידה","יוגורט","מעדן"]

def cat_of(name):
    low=name.lower()
    for b in BLACKLIST:
        if b in low: return "BLACKLIST"
    for c,kws in CATEGORIES.items():
        for kw in kws:
            if kw in name: return c
    return None

OUT=[]
for user,chain,store in [("TivTaam","7290873255550","010"),("Keshet","7290785400000","015")]:
    s=requests.Session();s.verify=False;s.headers.update({"User-Agent":"Mozilla/5.0"})
    t=login(s,user)
    files=lst(s,t)
    tgt=sorted([f for f in files if "PriceFull" in f and chain in f and any(seg==store for seg in f.replace(".gz","").split("-")[1:])])[-1]
    raw=s.get(f"{BASE}/file/d/{tgt}",timeout=120).content
    root=ET.fromstring(gzip.decompress(raw))
    s.close()
    OUT.append(f"\n{'='*55}\n{user} (סניף {store})")

    white=[]; unclassified=[]
    for it in root.findall(".//Item"):
        if (it.findtext("bIsWeighted") or "0")!="1": continue
        nm=(it.findtext("ItemName") or "").strip()
        if not nm: continue
        c=cat_of(nm)
        if c=="בשר לבן": white.append(nm)
        elif c is None: unclassified.append(nm)

    OUT.append(f"\n[בשר לבן - מסווג כרגע: {len(white)}]")
    for n in sorted(set(white)): OUT.append(f"  ✓ {n}")

    # חפש שקילים לא מסווגים שאולי הם בשר לבן/חזיר
    pork_hints=["חזיר","קסלר","פטיט","אמסטר","שפונדרה","פרושוטו","פנצ'טה","וירשט","פורק","חזה חזיר","קותלי","קרעקוב","סלו","שפק","בקון"]
    OUT.append(f"\n[שקילים לא-מסווגים עם רמז לבשר לבן/חזיר: ]")
    hits=[n for n in set(unclassified) if any(h in n for h in pork_hints)]
    for n in sorted(hits): OUT.append(f"  ? {n}")
    OUT.append(f"  (מתוך {len(set(unclassified))} שקילים לא-מסווגים בסך הכל)")

import os
os.makedirs("output",exist_ok=True)
open("output/diagnose_output.txt","w",encoding="utf-8").write("\n".join(OUT))
print("done")
