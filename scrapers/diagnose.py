"""
סקריפט אבחון - מגלה את המבנה האמיתי של ה-XML
ומדפיס אילו StoreId קיימים בפועל
"""
import gzip, io, ftplib
import xml.etree.ElementTree as ET

CHAINS = {
    "tivtaam": {"name": "טיב טעם", "ftp_user": "TivTaam", "chain_id": "7290873255550"},
    "keshet":  {"name": "קשת טעמים", "ftp_user": "Keshet", "chain_id": "7290785400000"},
}
HOST = "url.retail.publishedprices.co.il"

def run():
    for key, cfg in CHAINS.items():
        print(f"\n{'='*60}\n{cfg['name']} ({cfg['ftp_user']})")
        try:
            ftp = ftplib.FTP(HOST)
            ftp.login(cfg["ftp_user"], "")
        except Exception as e:
            print(f"  FTP login failed: {e}")
            continue

        ftp.cwd("/")
        entries = []
        ftp.dir(entries.append)
        price_files = []
        for entry in entries:
            fn = entry.split()[-1]
            if "PriceFull" in fn and cfg["chain_id"] in fn:
                price_files.append(fn)

        print(f"  PriceFull files: {len(price_files)}")
        # הדפס דוגמאות של שמות קבצים (השם מכיל את מספר הסניף)
        for fn in price_files[:8]:
            print(f"    {fn}")

        if not price_files:
            ftp.quit(); continue

        # הורד את הראשון ובדוק מבנה
        fn = price_files[0]
        buf = io.BytesIO()
        ftp.retrbinary(f"RETR {fn}", buf.write)
        ftp.quit()
        buf.seek(0)
        try:
            content = gzip.open(buf, 'rb').read()
        except Exception:
            buf.seek(0); content = buf.read()

        root = ET.fromstring(content)
        print(f"\n  Root tag: {root.tag}")
        # הדפס שדות ברמת הroot
        for child in list(root)[:12]:
            txt = (child.text or "").strip()
            if txt and len(txt) < 40:
                print(f"    <{child.tag}> = {txt}")

        # מצא את הItem הראשון והדפס את כל השדות שלו
        first_item = root.find(".//Item")
        if first_item is not None:
            print(f"\n  First <Item> fields:")
            for f in first_item:
                print(f"    <{f.tag}> = {(f.text or '')[:40]}")
        items = root.findall(".//Item")
        print(f"\n  Total items in this file: {len(items)}")

run()
