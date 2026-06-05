"""בדוק אילו קבצי PriceFull זמינים בפורטל ומה התאריכים שלהם"""
import gzip, re, json
import requests, urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
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
    r=s.post(f"{BASE}/file/json/dir",timeout=60,data=d,
             headers={"Referer":f"{BASE}/file","X-CSRFToken":t or "","X-Requested-With":"XMLHttpRequest"})
    return [x.get("fname","") for x in r.json().get("aaData",[])]

OUT=[]
for user,chain,store in [("TivTaam","7290873255550","010"),("Keshet","7290785400000","015")]:
    s=requests.Session();s.verify=False;s.headers.update({"User-Agent":"Mozilla/5.0"})
    t=login(s,user)
    files=lst(s,t)
    pf=sorted([f for f in files if "PriceFull" in f and chain in f and
               any(seg==store or seg.lstrip("0")==store.lstrip("0")
                   for seg in f.replace(".gz","").split("-")[1:])])
    OUT.append(f"\n=== {user} (store {store}) ===")
    OUT.append(f"קבצי PriceFull זמינים: {len(pf)}")
    for f in pf:
        OUT.append(f"  {f}")
    s.close()

import os; os.makedirs("output",exist_ok=True)
open("output/diagnose_output.txt","w",encoding="utf-8").write("\n".join(OUT))
print("done")
