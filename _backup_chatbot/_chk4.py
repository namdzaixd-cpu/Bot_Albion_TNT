
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
import subprocess
# List ALL file_name in json_storage
r = subprocess.run(["curl","-s", f"{url}/rest/v1/json_storage?select=file_name",
                    "-H", f"apikey: {key}", "-H", f"Authorization: Bearer {key}"],
                   capture_output=True, text=True)
print("ALL_FILES:", r.stdout[:800])
print("=== now check albion item blob ===")
r2 = subprocess.run(["curl","-s", f"{url}/rest/v1/json_storage?file_name=eq.tnc_albion_item_v1.json&select=file_name",
                    "-H", f"apikey: {key}", "-H", f"Authorization: Bearer {key}"],
                   capture_output=True, text=True)
print("ITEM_BLOB_EXISTS:", r2.stdout[:200])
