import aikframe as F
import vetariasn as vt
import fastapi
from services.configs import config

YH = F.YunhuActivityManager()

@vt.http.post("/v1/yunhu-callback")
async def callback(req: fastapi.Request, antifake: str = ""):
    if antifake != config["antifake_key"]:
        return # Reject fake webhook
    await YH.receive_event(await req.json())