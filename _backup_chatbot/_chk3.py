
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
# list columns of json_storage
r = subprocess.run(["curl","-s","-w","\nHTTP:%{http_code}", f"{url}/rest/v1/json_storage?limit=1",
                    "-H", f"apikey: {key}", "-H", f"Authorization: Bearer {key}"],
                   capture_output=True, text=True)
print("SAMPLE_ROW:", r.stdout[:600])
