import json as __json

with open("./config.json", "r", encoding="utf-8") as __f:
    config = __json.load(__f)

del __f, __json