import vetariasn as vt
import sqlalchemy as sa
from services.yhlink import YH
import aikframe as Aik
import openai
from services.configs import config

class ChatMessageModel(vt.orm.Base):
    __tablename__ = "aichat_message"
    seq: int = sa.Column(sa.BigInteger(), primary_key=True, default=vt.algo.calc_seqid)
    user: str = sa.Column(sa.String(20), primary_key=True)
    query: str = sa.Column(sa.Text(), nullable=False)
    answer: str = sa.Column(sa.Text(), nullable=False)

client = openai.AsyncOpenAI(api_key=config["ai_api"].get("apikey"), base_url=config["ai_api"].get("base_url"))

async def inference(query: str, history: list[ChatMessageModel] = [], knowledges: list[str] = []):
    # moderation
    C = query.lower()
    for ill in config["banwords"]:
        if ill.lower() in C:
            yield ("拒绝回答：不要发送违规消息！", )
            return
    del C
    # Build structure
    history.sort(key=lambda x: x.seq)
    messages = [{"role": "system", "content": "\n".join(config["system_prompt"])}]
    if len(knowledges) >= 0:
        knowledges = [ k.strip() for k in knowledges ]
        knowledges = [ (f"[item]\n{k}\n[/item]" if ("\n" in k) else f"[item]{k}[/item]") for k in knowledges ]
        messages.append({"role": "user", "content": "请记住这些知识：\n" + "\n".join(knowledges)})
        messages.append({"role": "assistant", "content": "好的，我已记住这些知识。"})
    for h in history:
        messages.append({"role": "user", "content": h.query})
        messages.append({"role": "assistant", "content": h.answer})
        del h
    messages.append({"role": "user", "content": query})
    del history
    stop_reason = "stop"
    async for chunk in await client.chat.completions.create(messages=messages, model="LongCat-Flash-Chat", temperature=0.1, stream=True, max_tokens=3000):
        delta = chunk.choices[0].delta
        if delta.content:
            yield str(delta.content)
        if chunk.choices[0].finish_reason:
            stop_reason = chunk.choices[0].finish_reason
    if stop_reason != "stop":
        yield ("\n\n拒绝回答：资源使用超限！", )
        return

async def query_history(user: str):
    async with vt.orm.Session() as session:
        return [ n._tuple()[0] for n in (await session.execute(
            sa.select(ChatMessageModel)
            .where(ChatMessageModel.user == user)
            .order_by(sa.desc(ChatMessageModel.seq))
            .limit(12)
        )).fetchall() ]

async def write_history(user: str, query: str, answer: str):
    async with vt.orm.Session() as session:
        session.add(ChatMessageModel(user=user, query=query, answer=answer))
        await session.commit()

@YH.register_message(allow_instruct=False)
async def normal_message_trigger(e: Aik.MessageModel):
    if e.session.recvType == "group" or e.content.method not in ["text", "markdown"]:
        return
    await private_chat_action(e.sender.senderId, e.content.text)

@YH.register_instruct(config["actions"]["question"])
async def instruct_trigger(e: Aik.MessageModel):
    if e.session.recvType == "group":
        await group_chat_action(e.session.recvId, f"请问：{e.content.text}")
    else:
        await private_chat_action(e.sender.senderId, f"请问：{e.content.text}")

async def private_chat_action(user: str, content: str):
    async with vt.mutex.MutexContext(f"aichat:{user}", ttl=3600):
        try:
            result = ""
            async with Aik.send_streaming_message(("user", user), method="markdown") as S:
                async for c in inference(content, await query_history(user)):
                    if isinstance(c, tuple):
                        await S.attach(c)
                        return
                    result += c
                    await S.attach(c)
                await write_history(user, content, result)
        except Exception as e:
            await Aik.send_message(("user", user), content=f"系统错误：{type(e).__name__}: {repr(e)}\nTrackback: \n{repr(e.__traceback__)}", method="text")

async def group_chat_action(group: str, content: str):
    try:
        async with Aik.send_streaming_message(("group", group), method="markdown") as S:
            async for c in inference(content, []):
                if isinstance(c, tuple):
                    await S.attach(c)
                    return
                await S.attach(c)
    except Exception as e:
        await Aik.send_message(("group", group), f"系统错误：{type(e).__name__}: {repr(e)}\nTrackback: \n{repr(e.__traceback__)}", method="text")

