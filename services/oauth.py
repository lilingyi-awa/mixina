import vetariasn as vt
import sqlalchemy as sa
from services.yhlink import YH
import aikframe as Aik
from services.configs import config
import random
import asyncio
import re
import time
import typing
import urllib.parse as P
from fastapi.responses import HTMLResponse, JSONResponse
import hashlib
import random
import fastapi
import aiohttp
import datetime
from fastapi.params import Form

def generate_aincode() -> str:
    return "-".join([ "".join([ random.choice("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz") for _ in range(0, 5) ]) for _ in range(0, 5) ])

class AuthPINModel(vt.transient.Base):
    __tablename__ = "oauth_pin"
    ainhash: int = sa.Column(sa.BigInteger(), primary_key=True)
    expires: int = sa.Column(sa.BigInteger(), nullable=False, default=int(time.time()) + 600)
    redirect_uri: int = sa.Column(sa.Text(), nullable=False)
    client_id: str = sa.Column(sa.String(32), nullable=False)

class AuthcodeModel(vt.orm.Base):
    __tablename__ = "oauth_authcode"
    aid: int = sa.Column(sa.BigInteger(), primary_key=True)
    uid: int = sa.Column(sa.BigInteger(), nullable=False)
    client_id: str = sa.Column(sa.String(32), nullable=False)
    expires: int = sa.Column(sa.BigInteger(), nullable=False, default=int(time.time()) + 3600)

@vt.register_daemon()
async def clear_expired_pin():
    while True:
        await asyncio.sleep(30)
        try:
            async with vt.transient.Session() as session:
                await session.execute(sa.delete(AuthPINModel).where(AuthPINModel.expires <= int(time.time())))
                await session.commit()
        except Exception:
            pass

@vt.register_daemon()
async def clear_expired_authcode():
    while True:
        await asyncio.sleep(10)
        try:
            async with vt.orm.Session() as session:
                await session.execute(sa.delete(AuthcodeModel).where(AuthcodeModel.expires <= int(time.time())))
                await session.commit()
            await asyncio.sleep(35)
        except Exception:
            pass

MD5CODE_MATCH = re.compile(r"^[a-f0-9]{32}$")
AUTHALGO_MATCH = re.compile(r"^[a-f0-9]{33,}$")

class AuthAlgo:
    @staticmethod
    def encode(aid: int, uid: int, appid: int = 0):
        SECRET = config["env"]["YUNHU_API_TOKEN"]
        PdS = hashlib.md5(aid.to_bytes(8, 'little') + uid.to_bytes(8, 'little') + SECRET.encode("ascii") + appid.to_bytes(4, 'little')).hexdigest()
        return PdS[:16] + hex(aid)[2:] + PdS[-16:]
    @staticmethod
    def decode(code: str):
        if not AUTHALGO_MATCH.match(code):
            return -1
        try:
            return int(code[16:-16], base=16)
        except Exception:
            return -1
    @staticmethod
    def verify(aid: int, uid: int, code: str, appid: int = 0):
        SECRET = config["env"]["YUNHU_API_TOKEN"]
        PdS = hashlib.md5(aid.to_bytes(8, 'little') + uid.to_bytes(8, 'little') + SECRET.encode("ascii") + appid.to_bytes(4, 'little')).hexdigest()
        return (code[:16] == PdS[:16]) and (code[-16:] == PdS[-16:])

class PageResponse(HTMLResponse):
    def __init__(self, content = None, status_code = 200, headers = None, media_type = None, background = None):
        estyle = "a{color: black; text-decoration: underline;}\ba:hover{color: #222; text-decoration: none;}"
        content = f"""
<!DOCTYPE>
<html>
    <head>
        <meta charset="utf-8"/>
        <style>{estyle}</style>
    </head>
    <body>
        <h1>云湖统一登录</h1>
        <hr/>
        {content}
        <hr/>
        <p>本服务由机器人 <a href="https://yhfx.jwznb.com/share?key=ZQwGk5mtTO1z&ts=1761015272" target="_blank">Vsinger小冰</a> 提供，与云湖官方无关</p>
        <p>最终解释权归何明所有</p>
    <body>
</html>
        """.strip()
        super().__init__(content, status_code, headers, media_type, background)

@vt.http.get("/oauth/authorize")
async def request_grant(client_id: str, redirect_uri: str, state: typing.Optional[str] = None):
    # Check request
    if not MD5CODE_MATCH.match(client_id):
        return PageResponse("错误：Client ID有误", 400)
    domain = P.urlparse(redirect_uri).hostname
    if domain == "":
        return PageResponse("错误：输入域名有误", 400)
    # Inject state
    if "?" in redirect_uri:
        if not redirect_uri.endswith("&"):
            redirect_uri += "&"
    else:
        redirect_uri += "?"
    if state is not None:
        redirect_uri += f"state={P.quote(state)}&"
    # Generate
    aincode = generate_aincode()
    async with vt.transient.Session() as session:
        session.add(AuthPINModel(
            ainhash=vt.algo.calc_hash(aincode),
            redirect_uri=redirect_uri,
            client_id=client_id
        ))
        await session.commit()
    # Print info
    return PageResponse(f"""
<p>您的验证序列：{aincode}</p>
<p>请添加云湖机器人：<a href="https://yhfx.jwznb.com/share?key=ZQwGk5mtTO1z&ts=1761015272" target="_blank">Vsinger小冰</a>（ID：83794852），并向“OAuth验证”指令传入该序列。</p>
<p>验证序列五分钟内有效，超过五分钟请刷新页面重新获取。</p>
""")

AUTHCODE_MATCH = re.compile(r"^[a-zA-Z0-9]{5}(\-[a-zA-Z0-9]{5}){4}$")

async def shortlize_url(redirect_uri):
    try:
        async with aiohttp.ClientSession() as session:
            result = (await (await session.post(
                url="https://monojson.com/api/short-link",
                json={"url": redirect_uri}
            )).json())["shortUrl"]
            if not isinstance(result, str):
                return redirect_uri
            if not result.startswith("https://monojson.com/s/"):
                return redirect_uri
            return result
    except Exception:
        return redirect_uri

@YH.register_instruct(config["actions"]["oauth"])
async def authorize(e: Aik.MessageModel):
    if not AUTHCODE_MATCH.match(e.content.text):
        await Aik.send_message(e.session, content="验证序列不符合格式！", method="text", parentId=e.msgId)
    # Security filter
    if e.session.recvType == "group":
        async with vt.transient.Session() as session:
            await session.execute(sa.delete(AuthPINModel).where(AuthPINModel.ainhash == vt.algo.calc_hash(e.content.text)))
            await session.commit()
        await Aik.send_message(e.session, content="此操作在群聊中极不安全，您的验证序列已经作废，请重新获取序列后在私聊中操作！", method="text", parentId=e.msgId)
    # pick key
    async with vt.transient.Session() as session:
        result = (await session.execute(sa.select(AuthPINModel).where(AuthPINModel.ainhash == vt.algo.calc_hash(e.content.text)))).fetchone()
        if result is None:
            asyncio.create_task(Aik.send_message(e.session, content="验证序列不存在！", method="text", parentId=e.msgId))
            return
        atc = result._tuple()[0]
        client_id = atc.client_id
        redirect_uri = atc.redirect_uri
        await session.delete(atc)
        await session.commit()
        del atc
    # Create authcode
    aid = vt.algo.calc_seqid()
    uid = int(e.sender.senderId)
    redirect_uri += "code=" + P.quote(AuthAlgo.encode(aid, uid, appid=1405))
    async with vt.orm.Session() as session:
        session.add(AuthcodeModel(
            aid=aid,
            uid=uid,
            client_id=client_id
        ))
        await session.commit()
    # Shortlize
    redirect_uri = await shortlize_url(redirect_uri)
    # Response
    await Aik.send_message(e.session, content=f"请点击如下链接登录：\n<{redirect_uri}>", method="markdown", parentId=e.msgId)

@vt.http.get("/oauth/token")
async def get_token(code: str, client_id: str, client_secret: str):
    if not MD5CODE_MATCH.match(client_id) or client_id != hashlib.md5(client_secret.encode("utf-8")).hexdigest():
        return JSONResponse({"msg": "wrong client id"}, 401)
    aid = AuthAlgo.decode(code)
    if aid == -1:
        return JSONResponse({"msg": "wrong authcode"}, 401)
    async with vt.orm.Session() as session:
        result = (await session.execute(
            sa.select(AuthcodeModel)
            .where(AuthcodeModel.aid == aid)
            .where(AuthcodeModel.client_id == client_id)
            .where(AuthcodeModel.expires >= int(time.time()))
        )).fetchone()
        if result is None:
            return JSONResponse({"msg": "wrong authcode"}, 401)
        esa = result._tuple()[0]
        uid = esa.uid
        if not AuthAlgo.verify(aid, uid, code, appid=1405):
            return JSONResponse({"msg": "wrong authcode"}, 401)
        await session.delete(esa)
        await session.commit()
    access_token = AuthAlgo.encode(uid, vt.algo.calc_hash(client_id), appid=42) # Black magic
    return JSONResponse({
        "access_token": access_token,
        "refresh_token": access_token,
        "token_type": "bearer",
        "expires_in": 86400 * 365
    })

@vt.http.post("/oauth/token")
async def get_token_post(code: typing.Annotated[str, Form()], client_id: typing.Annotated[str, Form()], client_secret: typing.Annotated[str, Form()]):
    return await get_token(code, client_id, client_secret)

@vt.http.get("/oauth/appcall/{client_id}/identity")
async def get_identity_get(client_id: str, req: fastapi.Request):
    access_token = ""
    if "access_token" in req.query_params:
        access_token = req.query_params["access_token"]
    elif "Authorization" in req.headers:
        if not req.headers["Authorization"].startswith("Bearer "):
            return JSONResponse({"msg": "wrong authcode"}, 401)
        access_token = req.headers["Authorization"].removeprefix("Bearer ")
    else:
        return JSONResponse({"msg": "wrong authcode"}, 401)
    return await get_identity_post(client_id, access_token)

@vt.http.post("/oauth/appcall/{client_id}/identity")
async def get_identity_post(client_id: str, access_token: typing.Annotated[str, Form()]):
    # Verify
    uid = AuthAlgo.decode(access_token)
    if uid == -1 or not AuthAlgo.verify(uid, vt.algo.calc_hash(client_id), access_token, appid=42):
        return JSONResponse({"msg": "wrong authcode"}, 401)
    async with aiohttp.ClientSession() as session:
        result = (await (await session.get(url=f"https://chat-web-go.jwzhd.com/v1/user/homepage?userId={uid}")).json())["data"]["user"]
    # Build info
    created = datetime.datetime.fromtimestamp(result["registerTime"]).isoformat("T") + "Z"
    nowtime = datetime.datetime.now().isoformat("T") + "Z"
    return JSONResponse({
        "id": uid,
        "login": f"yh{uid}",
        "login_name": "",
        "source_id": 0,
        "full_name": result["nickname"],
        "email": f"{uid}@yhchat.com",
        "avatar_url": result["avatarUrl"].replace("https://chat-img.jwznb.com/", "https://chat-webp.000434.xyz/"),
        "html_url": f"https://www.yhchat.com/user/homepage/{uid}",
        "language": "zh-CN",
        "is_admin": False,
        "last_login": nowtime,
        "created": created,
        "restricted": False,
        "active": True,
        "prohibit_login": False,
        "location": "",
        "website": "",
        "description": "",
        "visibility": "public",
        "followers_count": 0,
        "following_count": 0,
        "starred_repos_count": 0,
        "username": f"yh{uid}"
    })