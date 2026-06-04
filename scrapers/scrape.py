"""
בדיקה: האם רוסמן מדווחת לפורטל ויש לה נתונים?
מנסה כמה שמות משתמש אפשריים ובודק התחברות + קבצים
"""
import re, gzip, traceback
import requests, urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import xml.etree.ElementTree as ET

BASE = "https://url.publishedprices.co.il"

# שמות משתמש אפשריים לרוסמן (הפורטל משתמש בשם הרשת באנגלית)
CANDIDATES = ["Rosman", "rosman", "RoshMan", "Roshman", "ROSMAN",
              "RosmanShivuk", "rosmanshivuk", "Rosman1"]

LOG = []
def log(s): LOG.append(str(s)); print(s)

def find_token(html):
    for p in [r'name=["\']csrftoken["\']\s+value=["\']([^"\']+)',
              r'<meta\s+name=["\']csrftoken["\']\s+content=["\']([^"\']+)']:
        m = re.search(p, html, re.I)
        if m: return m.group(1)
    return None

def try_login(user, pw=""):
    s = requests.Session(); s.verify = False
    s.headers.update({"User-Agent": "Mozilla/5.0"})
    r = s.get(f"{BASE}/login", timeout=30)
    t = find_token(r.text)
    pl = {"username": user, "password": pw, "Submit": "Sign in"}
    if t: pl["csrftoken"] = t
    r = s.post(f"{BASE}/login/user", data=pl, timeout=30,
               headers={"Referer": f"{BASE}/login"})
    chk = s.get(f"{BASE}/file", timeout=30)
    # אם ה-URL הסופי הוא /file (לא חזרה ל-login) => התחברות הצליחה
    success = chk.url.rstrip("/").endswith("/file")
    fresh = find_token(chk.text) or t
    return s, success, fresh

def list_files(s, t):
    d = {"sEcho":"1","iColumns":"5","sColumns":",,,,","iDisplayStart":"0",
         "iDisplayLength":"100000","mDataProp_0":"fname","sSearch":"","cd":"/"}
    if t: d["csrftoken"] = t
    r = s.post(f"{BASE}/file/json/dir", timeout=60, data=d,
               headers={"Referer":f"{BASE}/file","X-CSRFToken":t or "",
                        "X-Requested-With":"XMLHttpRequest"})
    try:
        data = r.json()
    except Exception:
        return [], "not-json"
    return [row.get("fname","") for row in data.get("aaData", [])], data.get("error")

log("חיפוש רוסמן בפורטל publishedprices:\n")
found_user = None
for user in CANDIDATES:
    try:
        s, ok, t = try_login(user)
        log(f"  {user}: login={'✓' if ok else '✗'}")
        if ok:
            files, err = list_files(s, t)
            log(f"      files: {len(files)}  error={err}")
            # זהה chain_id מהקבצים
            price_files = [f for f in files if "Price" in f]
            if price_files:
                log(f"      sample: {price_files[0]}")
                # chain id = הספרות הארוכות בשם
                m = re.search(r'(\d{13})', price_files[0])
                if m: log(f"      chain_id: {m.group(1)}")
                found_user = user
        s.close()
    except Exception as e:
        log(f"  {user}: ERROR {e}")

if not found_user:
    log("\n⚠ לא נמצאה התחברות בשמות שניסיתי.")
    log("הרשתות הגדולות בפורטל הזה: TivTaam, Keshet, osherad, HaziHinam, Yohananof, ...")
    log("רוסמן אולי מדווחת לפורטל אחר (cerberus/matrix) או תחת שם אחר.")

import os
os.makedirs("output",exist_ok=True)
open("output/diagnose_output.txt","w",encoding="utf-8").write("\n".join(LOG))
