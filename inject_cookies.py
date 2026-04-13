import sqlite3, json

DB = "/app/storage/twscrape.db"
COOKIES_FILE = "/app/storage/cookie_sonar.json"
USERNAME = "alexsonarp"

with open(COOKIES_FILE) as f:
    raw = json.load(f)

cookies_dict = {c["name"]: c["value"] for c in raw}
cookies_json = json.dumps(cookies_dict)

con = sqlite3.connect(DB)
cur = con.cursor()
cur.execute(
    "UPDATE accounts SET cookies = ?, active = 1 WHERE LOWER(username) = ?",
    (cookies_json, USERNAME.lower())
)
con.commit()
print("Filas actualizadas:", cur.rowcount)
con.close()
