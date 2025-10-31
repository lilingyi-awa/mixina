from services.yhlink import YH
import vetariasn as vt
import sqlalchemy as sa
import aikframe as Aik
from services.configs import config
import typing
import re

class CoinBalanceModel(vt.orm.Base):
    __tablename__ = "lilicoin_balance"
    uid: int = sa.Column(sa.BigInteger(), primary_key=True)
    balance: int = sa.Column(sa.BigInteger(), default=0)

class CoinService:
    @staticmethod
    async def transfer(
        sender: typing.Union[int, typing.Literal["system"]],
        target: typing.Union[int, typing.Literal["system"]],
        value: int
    ) -> typing.Literal["ok", "not-enough", "failed"]:
        if sender == "system" and target == "system":
            return "ok"
        try:
            async with vt.orm.Session() as session:
                # Sending
                if sender != "system":
                    oSender = (await session.execute(sa.select(CoinBalanceModel).where(CoinBalanceModel.uid == sender))).fetchone()
                    if oSender is None:
                        return "not-enough"
                    oSender = oSender._tuple()[0]
                    if oSender.balance < value:
                        return "not-enough"
                    elif oSender.balance == value:
                        await session.delete(oSender)
                    else:
                        oSender.balance -= value
                # Receiving
                if target != "system":
                    oReceiver = (await session.execute(sa.select(CoinBalanceModel).where(CoinBalanceModel.uid == target))).fetchone()
                    if oReceiver is None:
                        await session.execute(sa.insert(CoinBalanceModel).values(uid=target, balance=value))
                    else:
                        oReceiver = oReceiver._tuple()[0]
                        oReceiver.balance += value
                await session.commit()
                return "ok"
        except Exception:
            return "failed"
    @staticmethod
    async def get_balance(uid: int):
        try:
            async with vt.orm.Session() as session:
                oSender = (await session.execute(sa.select(CoinBalanceModel).where(CoinBalanceModel.uid == uid))).fetchone()
                if oSender is None:
                    return 0
                return oSender._tuple()[0].balance
        except Exception:
            return -1

TC_METHOD = re.compile(r"^([1-9][0-9]{3,})\|([1-9][0-9]*)$")

@YH.register_instruct(config["actions"]["transfer"])
async def yh_transfer(e: Aik.MessageModel):
    if e.content.method not in ["text", "markdown"]:
        return
    mat = TC_METHOD.match(e.content.text)
    if mat is None:
        await Aik.send_message(e.session, content="交易操作格式错误。", method="text", parentId=e.msgId)
        return
    target = int(mat.group(1))
    value = int(mat.group(2))
    res = await CoinService.transfer(sender=int(e.sender.senderId), target=target, value=value)
    await Aik.send_message(e.session, content={
        "ok": "转账成功！",
        "not-enough": "穷小子！你根本没有这么多钱！",
        "failed": "转账失败：系统错误。"
    }[res], method="text", parentId=e.msgId)

@YH.register_instruct(config["actions"]["balance"])
async def yh_balance(e: Aik.MessageModel):
    balance = await CoinService.get_balance(int(e.sender.senderId))
    if balance == -1:
        await Aik.send_message(e.session, content="无法获取您的余额，请稍后再试！", method="text", parentId=e.msgId)
    elif e.session.recvType == "group":
        await Aik.send_message(e.session, content=f"用户{e.sender.senderId}的琉璃币余额：{balance}", method="text", parentId=e.msgId)
    elif balance == 0:
        await Aik.send_message(e.session, content="穷光蛋，你一个子都没有！", method="text", parentId=e.msgId)
    elif balance <= 1000:
        await Aik.send_message(e.session, content=f"穷光蛋，你到底努不努力啊！怎么才有{balance}个琉璃币啊？", method="text", parentId=e.msgId)
    elif balance >= 100000:
        await Aik.send_message(e.session, content=f"富哥您好，你当前有{balance}琉璃币，请问还有什么需要帮助的吗？", method="text", parentId=e.msgId)
    else:
        await Aik.send_message(e.session, content=f"你的琉璃币余额：{balance}", method="text", parentId=e.msgId)