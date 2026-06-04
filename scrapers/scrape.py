"""
אבחון: מה מבחין מוצרי בשר/מעדנייה טריים מהרעש?
בודק ItemType, prefix של ItemCode, bIsWeighted, ודוגמאות
"""
import os, json, gzip, re, traceback
import requests, urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import xml.etree.ElementTree as ET

BASE = "https://url.publishedprices.co.il"
CHAINS = {
    "tivtaam": {"user":"TivTaam","password":"","chain_id":"7290873255550","store":"010"},
    "keshet":  {"user":"Keshet","password":"","chain_id":"7290785400000","store":"015"},
}
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

# מילות מפתח לבשר/מעדנייה טרי אמיתי
FRESH_HINTS = ["עוף","פרגית","שניצל","כרעיים","שוקיים","כנפיים","בקר","עגל","אנטריקוט",
               "אסאדו","טחון","סטייק","צלעות","כבד","פסטרמה","נקניק","סלמי","קבנוס",
               "גבינה","קממבר","מוצרלה","פטה","ברי","שינקן","הודו"]
NOISE = ["לכלב","לחתול","לגור","חתול","כלב","מזון","ציפס","צ'יפס","שבבי","מרק","אטריות",
         "תבלין","תיבול","ראמן","קוביות ציר","ציר ","אבקת","רוטב","ממרח","חטיף"]

def run():
    for key,cfg in CHAINS.items():
        log(f"\n{'='*60}\n{key} store {cfg['store']}")
        s=requests.Session(); s.verify=False
        s.headers.update({"User-Agent":"Mozilla/5.0"})
        t=login(s,cfg["user"],cfg["password"])
        files=list_files(s,t)
        tgt=pick(files,cfg["chain_id"],cfg["store"])
        log(f"file: {tgt}")
        raw=s.get(f"{BASE}/file/d/{tgt}",timeout=120).content
        try: content=gzip.decompress(raw)
        except: content=raw
        try: root=ET.fromstring(content)
        except: root=ET.fromstring(content.decode("utf-8-sig",errors="ignore"))
        items=root.findall(".//Item")
        log(f"total items: {len(items)}")

        # התפלגות ItemType
        from collections import Counter
        types=Counter(); code_prefix=Counter()
        weighted_fresh=0
        for it in items:
            itype=(it.findtext("ItemType") or "?").strip()
            types[itype]+=1
            code=(it.findtext("ItemCode") or "").strip()
            if code: code_prefix[code[:1]]+=1

        log(f"ItemType distribution: {dict(types)}")
        log(f"ItemCode first-digit distribution: {dict(code_prefix)}")

        # בדוק: בין המוצרים השקילים (bIsWeighted=1) - כמה הם בשר טרי?
        log("\n--- דוגמאות מוצרים שקילים (bIsWeighted=1) ---")
        cnt=0
        for it in items:
            if (it.findtext("bIsWeighted") or "0")=="1":
                name=(it.findtext("ItemName") or "").strip()
                code=(it.findtext("ItemCode") or "").strip()
                itype=(it.findtext("ItemType") or "").strip()
                log(f"  [{itype}] {code[:5]}.. {name[:40]}")
                cnt+=1
                if cnt>=20: break
        log(f"  סך שקילים: {sum(1 for it in items if (it.findtext('bIsWeighted') or '0')=='1')}")

        # בדוק כמה מהמוצרים מכילים hint אבל גם noise
        fresh_clean=0; fresh_noisy=0
        for it in items:
            name=(it.findtext("ItemName") or "").lower()
            has_hint=any(h in name for h in FRESH_HINTS)
            has_noise=any(n in name for n in NOISE)
            if has_hint and not has_noise: fresh_clean+=1
            elif has_hint and has_noise: fresh_noisy+=1
        log(f"\n  hint & clean: {fresh_clean} | hint & noise: {fresh_noisy}")
        s.close()

run()
import os
os.makedirs("output",exist_ok=True)
open("output/diagnose_output.txt","w",encoding="utf-8").write("\n".join(LOG))
