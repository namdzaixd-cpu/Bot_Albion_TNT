
import re
env = open(r"C:/Users/User/Documents/CODE/NDZ/Bot_Albion_TNC/.env", encoding="utf-8").read()
d = {}
for line in env.splitlines():
    line=line.strip()
    if not line or line.startswith("#"): continue
    if "=" in line:
        k,v = line.split("=",1)
        d[k]=v.strip().strip('"').strip("'")
key = d.get("SUPABASE_SERVICE_ROLE_KEY") or d.get("SUPABASE_ANON_KEY")
url = d.get("SUPABASE_URL")
import subprocess, json
r = subprocess.run(["curl","-s", f"{url}/rest/v1/json_storage?file_name=eq.tnc_albion_item_v1.json&select=data",
                    "-H", f"apikey: {key}", "-H", f"Authorization: Bearer {key}"],
                   capture_output=True, text=True)
out = r.stdout
print("RESP_LEN:", len(out))
bows = sorted(set(re.findall(r'T8_2H_BOW[A-Z_]*', out)))
print("ALL_BOW_UIDS:", bows)
names_badon = re.findall(r'"name"\s*:\s*"([^"]*badon[^"]*)"', out, re.I)
print("NAMES_BADON:", names_badon[:10])
# count total items
m = re.search(r'"items"\s*:\s*\{(.*)\}', out, re.S)
print("HAS_ITEMS_KEY:", bool(m))
