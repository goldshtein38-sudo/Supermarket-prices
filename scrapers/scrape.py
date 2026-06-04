"""
בודק אילו רשתות קיימות בפורטל publishedprices + מנסה את רוסמן בפורטל matrix
"""
import re
import requests, urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = "https://url.publishedprices.co.il"
LOG = []
def log(s): LOG.append(str(s)); print(s)

def find_token(html):
    for p in [r'name=["\']csrftoken["\']\s+value=["\']([^"\']+)',
              r'<meta\s+name=["\']csrftoken["\']\s+content=["\']([^"\']+)']:
        m = re.search(p, html, re.I)
        if m: return m.group(1)
    return None

def try_login(base, user, pw=""):
    s = requests.Session(); s.verify=False
    s.headers.update({"User-Agent":"Mozilla/5.0"})
    try:
        r = s.get(f"{base}/login", timeout=20)
    except Exception as e:
        return False, f"no-connect: {e}"
    t = find_token(r.text)
    pl = {"username":user,"password":pw,"Submit":"Sign in"}
    if t: pl["csrftoken"]=t
    try:
        s.post(f"{base}/login/user", data=pl, timeout=20, headers={"Referer":f"{base}/login"})
        chk = s.get(f"{base}/file", timeout=20)
        return chk.url.rstrip("/").endswith("/file"), chk.url
    except Exception as e:
        return False, str(e)
    finally:
        s.close()

# 1. אילו רשתות מוכרות קיימות בפורטל הזה?
log("=== רשתות מוכרות בפורטל publishedprices ===")
known = ["TivTaam","Keshet","osherad","Yohananof","HaziHinam","Rami_levy",
         "RamiLevy","SuperPharm","Maayan2000","freshmarket","Stop_Market",
         "politzer","Paz_yellow","Quik","Bareket","yuda_ho","Rosman","ZolVeBegadol"]
exist = []
for u in known:
    ok, info = try_login(BASE, u)
    mark = "✓" if ok else "✗"
    log(f"  {u}: {mark}")
    if ok: exist.append(u)
log(f"\nקיימות: {exist}")

# 2. נסה את רוסמן בפורטלים אחרים נפוצים
log("\n=== חיפוש רוסמן בפורטלים אחרים ===")
other_portals = [
    "https://prices.rosman.co.il",
    "https://rosman.binaprojects.com",
    "https://url.retail.publishedprices.co.il",
]
for portal in other_portals:
    for u in ["Rosman","rosman",""]:
        ok, info = try_login(portal, u) if u else (None, "skip")
        if u:
            log(f"  {portal} [{u}]: {'✓' if ok else '✗'} ({str(info)[:50]})")

import os
os.makedirs("output",exist_ok=True)
open("output/diagnose_output.txt","w",encoding="utf-8").write("\n".join(LOG))
