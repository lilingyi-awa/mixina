import vetariasn as vt
import fastapi
from fastapi.responses import JSONResponse, HTMLResponse
import os

@vt.http.exception_handler(404)
async def webpage_engine(req: fastapi.Request, *args, **kwargs):
    if req.method.lower() != "get":
        return JSONResponse({"detail": "Not Found"}, 404)
    if req.url.path in ["", "/"]:
        ES = "./static/index.html"
    else:
        ES = os.path.join("./static", req.url.path)
    if os.path.exists(ES):
        if os.path.isfile(ES):
            with open(ES, "r", encoding="utf-8") as f:
                return HTMLResponse(f.read())
        elif os.path.isdir(ES):
            ES = os.path.join(ES, "index.html")
            if os.path.exists(ES):
                with open(ES, "r", encoding="utf-8") as f:
                    return HTMLResponse(f.read())
    return JSONResponse({"detail": "Not Found"}, 404)