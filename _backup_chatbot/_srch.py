
import re, os
env = open(r"C:/Users/User/Documents/CODE/NDZ/Bot_Albion_TNC/.env", encoding="utf-8").read()
for line in env.splitlines():
    line=line.strip()
    if not line or line.startswith("#"): continue
    if "=" in line:
        k,v = line.split("=",1)
        os.environ[k]=v.strip().strip('"').strip("'")
import sys; sys.path.insert(0, r"C:/Users/User/Documents/CODE/NDZ/Bot_Albion_TNC/bot")
from core.data.albion_item import search_items, load_items
print("load_items items count:", len(load_items().get("items",{})))
for q in ["bow of badon","Bow of Badon","badon","bow badon","đọc skill bow of badon"]:
    r = search_items(q, 3)
    print(repr(q), "->", [(u, (it.get("name") if isinstance(it,dict) else "")) for u,it in (r or [])][:3] if r else "NONE")
