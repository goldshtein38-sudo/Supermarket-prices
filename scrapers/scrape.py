import gzip, re
import requests, urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import xml.etree.ElementTree as ET
BASE="https://url.publishedprices.co.il"
def ftok(h):
    m=re.search(r'name=["\']csrftoken["\']\s+value=["\']([^"\']+)',h,re.I); return m.group(1) if m else None
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

OUT=[]
for user,chain,store in [("TivTaam","7290873255550","010"),("Keshet","7290785400000","015")]:
    s=requests.Session();s.verify=False;s.headers.update({"User-Agent":"Mozilla/5.0"})
    t=login(s,user)
    files=lst(s,t)
    # הקובץ שנבחר ע"י pick()
    c=[f for f in files if "PriceFull" in f and chain in f and any(seg==store or seg.lstrip("0")==store.lstrip("0") for seg in f.replace(".gz","").split("-")[1:])]
    chosen=sorted(c)[-1] if c else None
    OUT.append(f"\n=== {user} (store={store}) ===")
    OUT.append(f"קובץ שנבחר: {chosen}")
    OUT.append(f"מס' קבצים תואמים: {len(c)}")
    # הורד ובדוק StoreID בפנים
    if chosen:
        raw=s.get(f"{BASE}/file/d/{chosen}",timeout=120).content
        root=ET.fromstring(gzip.decompress(raw))
        sid=root.find(".//StoreID") or root.find(".//StoreId")
        OUT.append(f"StoreID בתוך הקובץ: {sid.text.strip() if sid is not None else '?'}")
    # מצא את שם הסניף מקובץ Stores
    sf=[f for f in files if f.startswith("Stores") and chain in f]
    if sf:
        raw=s.get(f"{BASE}/file/d/{sorted(sf)[-1]}",timeout=120).content
        try: sroot=ET.fromstring(gzip.decompress(raw))
        except: sroot=ET.fromstring(raw)
        for st in sroot.iter():
            if st.tag in ("Store","STORE","Branch"):
                sid=name=city=""
                for ch_ in st:
                    if ch_.tag in ("StoreID","StoreId"): sid=(ch_.text or "").strip()
                    if ch_.tag in ("StoreName","StoreNm"): name=(ch_.text or "").strip()
                    if ch_.tag=="City": city=(ch_.text or "").strip()
                if sid.lstrip("0")==store.lstrip("0"):
                    OUT.append(f"שם הסניף לפי קובץ Stores: StoreID={sid} | שם='{name}' | עיר='{city}'")
    s.close()
import os; os.makedirs("output",exist_ok=True)
open("output/diagnose_output.txt","w",encoding="utf-8").write("\n".join(OUT))
print("done")
