from nonebot.adapters.onebot.v11.bot import Bot
from nonebot.adapters.onebot.v11.event import MessageEvent
from nonebot.adapters.onebot.v11 import Message
from nonebot.params import CommandArg
from nonebot.exception import FinishedException
from nonebot import on_command
import json
import traceback
import re
from urllib import request as req

ctrlGroup = json.load(open("data/ctrl.json", encoding="utf-8"))["control"]
linuxkernelnews = on_command("linuxkernelnews",aliases={"lkn"})

@linuxkernelnews.handle()
async def linuxkernelnewsHandle(
        bot: Bot,
        event: MessageEvent,
        message: Message = CommandArg()):
    try:
        with req.urlopen(f"https://www.kernel.org/feeds/kdist.xml") as fp:
            data = fp.read()
        data=re.findall(r'https://cdn.kernel.org/pub/linux/kernel/*./linux-.*.tar.xz"',data)
        kernels=[]
        for i in data:
            index=data.index(i)
            i=i[:-1]
            kernels+=f"{index}. {i}\n"
        answer=f"""kernel.org最新可用内核:
{kernels}
"""
        await linuxkernelnews.finish(answer)
    except FinishedException:
        raise FinishedException()
    except Exception:
        await bot.send_group_message(
            message=traceback.format_exc(),
            group_id=ctrlGroup
        )
    await linuxkernelnews.finish("处理失败")

# [HELPSTART] Version: 2
# Command: linuxkernelnews
# Info: linuxkernelnews（查看最新的linux内核）
# [HELPEND]
