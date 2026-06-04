"""
בודק אם רוסמן מפרסם בפורטל publishedprices - מנסה שמות משתמש אפשריים
וגם בודק את רשימת הרשתות הזמינות בפורטל
"""
import re, requests, urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = "https://url.publishedprices.co.il"

# שמות משתמש אפשריים לרוסמן (הפורטל משתמש בשם הרשת כ-username)
candidates = ["Rosman", "rosman", "RosmanMarket", "Rosman-Market", "RosmanMarketing",
              "maadaney-rosman", "MaadaneyRosman", "rosman-market", "RosmanLogistics"]

def find_token(html):
    for p in [r'name=["\']csrftoken["\']\s+value=["\']([^"\']+)',
              r'<meta\s+name=["\']csrftoken["\']\s+content=["\']([^"\']+)']:
        m=re.search(p,html,re.I)
        if m: return m.group(1)
    return None

OUT=["בדיקת רוסמן בפורטל:\n"]
def p(x): OUT.append(x); print(x)

for user in candidates:
    s = requests.Session(); s.verify=False
    s.headers.update({"User-Agent":"Mozilla/5.0"})
    try:
        r = s.get(f"{BASE}/login", timeout=20)
        token = find_token(r.text)
        pl = {"username": user, "password": "", "Submit": "Sign in"}
        if token: pl["csrftoken"] = token
        r = s.post(f"{BASE}/login/user", data=pl, timeout=20, headers={"Referer": f"{BASE}/login"})
        chk = s.get(f"{BASE}/file", timeout=20)
        # אם הגענו ל-/file ולא חזרנו ל-login => המשתמש קיים
        success = "/file" in chk.url and "login" not in chk.url.lower()
        p(f"  {user:20s} -> login url: {chk.url.split('/')[-1] or 'file'}  {'✓ EXISTS' if success else '✗'}")
    except Exception as e:
        p(f"  {user:20s} -> error: {e}")
    s.close()

import os
os.makedirs("output",exist_ok=True)
open("output/diagnose_output.txt","w",encoding="utf-8").write("\n".join(OUT))
