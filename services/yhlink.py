import aikframe as F
import vetariasn as vt
import fastapi

YH = F.YunhuActivityManager()

@vt.http.post("/v1/yunhu-callback")
async def callback(req: fastapi.Request):
    await YH.receive_event(await req.json())