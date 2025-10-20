from services.yhlink import YH
import aikframe as Aik
from services.configs import config

@YH.register_instruct(config["actions"]["topnote"])
async def set_topnote(e: Aik.MessageModel):
    content = e.content.text
    if content == " ":
        content = ""
    await Aik.set_board(e.session, content=content, method=e.content.method)

@YH.register_message(False)
async def detect_illegal(e: Aik.MessageModel):
    if e.session.recvType == "user" or e.content.method not in ["text", "markdown", "html"]:
        return
    if e.sender.senderId in config["group_banusers"] and e.sender.senderLevel != "owner":
        await Aik.send_message(e.session, content="警报：这里有一条违规消息！", method='text', parentId=e.msgId) # Ban user
        return
    C = e.content.text.lower()
    for ill in config["banwords"]:
        if ill.lower() in C:
            await Aik.send_message(e.session, content="警报：这里有一条违规消息！", method='text', parentId=e.msgId)
            return

@YH.register_user_joined()
async def detect_join(e: Aik.UserChangedModel):
    await Aik.send_message(("group", e.group), content=f"欢迎用户{e.user}进群！", method='text')

@YH.register_user_leaved()
async def detect_leave(e: Aik.UserChangedModel):
    await Aik.send_message(("group", e.group), content=f"用户{e.user}好像退群了？", method='text')

@YH.register_user_followed()
async def detect_follow(e: Aik.UserChangedModel):
    await Aik.send_message(("user", e.user), content=f"你好，我是小冰。请问有什么需要帮助的吗？", method='text')