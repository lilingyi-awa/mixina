import json as __json
import vetariasn as vt
import asyncio

with open("./config.json", "r", encoding="utf-8") as __f:
    config = __json.load(__f)

del __f

@vt.register_daemon()
async def swap_config():
    global config
    await asyncio.sleep(10)
    while True:
        try:
            with open("./config.json", "r", encoding="utf-8") as __f:
                config = __json.load(__f)
            await asyncio.sleep(10)
        except Exception:
            await asyncio.sleep(1)