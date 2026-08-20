import re, os
env = open(r"C:/Users/User/Documents/CODE/NDZ/Bot_Albion_TNC/.env", encoding="utf-8").read()
for line in env.splitlines():
    line=line.strip()
    if not line or line.startswith("#"): continue
    if "=" in line:
        k,v = line.split("=",1)
        os.environ[k]=v.strip().strip('"').strip("'")
import sys; sys.path.insert(0, "bot")
from core.data.albion_item import load_items, format_item_full
idx = load_items()
it = idx["items"]["T8_2H_BOW_KEEPER"]
print("NAME:", it.get("name"), "| name_vi:", it.get("name_vi"))
sp = it.get("spells", {})
print("active count:", len(sp.get("active",[])), "| passive count:", len(sp.get("passive",[])))
for s in sp.get("active",[]):
    print("  ACT slot=", s.get("slot"), "tag=", s.get("tag"), "name=", s.get("name_en") or s.get("name_vi"), "remove=", s.get("remove"))
for s in sp.get("passive",[]):
    print("  PAS name=", s.get("name_en") or s.get("name_vi"), "remove=", s.get("remove"))
print("---- FORMAT ITEM FULL ----")
print(format_item_full("T8_2H_BOW_KEEPER", it, max_chars=2000))
