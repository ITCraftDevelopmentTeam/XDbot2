import asyncio
import json
import os
import os.path
import random
import time
import traceback
import marshal
import re
from typing import cast
from . import _error
from .etm import exp, economy
from . import _lang, _messenger
import httpx
from ._utils import Json, finish, context_review
from nonebot import on_command, get_app, on_message
from nonebot.adapters.onebot.v11 import (
    Bot,
    Message,
    GroupMessageEvent,
    MessageEvent,
    MessageSegment,
)
from nonebot.permission import SUPERUSER
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot.rule import to_me
from typing import TypedDict


class CaveMessage(TypedDict):
    message_id: int
    cave_id: str


cave_comment = on_message(rule=to_me())
cave_confirm_add = on_message(rule=to_me())
cave_confirm = {}
ctrlGroup = json.load(open("data/ctrl.json", encoding="utf-8"))["control"]
latest_use = time.time()
cave_messages: list[CaveMessage] = []
path = os.path.abspath(os.path.dirname("."))
app = get_app()
commandHelp = {
    "cave": {
        "name": "cave",
        "info": "随机、投稿或查询 回声洞",
        "msg": "回声洞",
        "usage": [
            "cave：随机一条回声洞",
            "cave-a <内容>：投稿一条回声洞（见cave(1)）",
            "cave-s：查看回声洞状态",
            "cave-c <ID> <内容...>：添加评论",
        ],
    }
}
MAX_NODE_MESSAGE = 100


async def showEula(user_id, matcher=Matcher()):
    if not Json("cave.showeula.json")[user_id]:
        await matcher.send(
            "如果开始使用 回声洞，即代表您同意《XDbot2 回声洞 用户协议》（https://github.com/ITCraftDevelopmentTeam/XDbot2/discussions/370）",
            at_sender=True,
        )
        Json("cave.showeula.json")[user_id] = True


@cave_comment.handle()
async def cave_comment_writer(event: GroupMessageEvent):
    try:
        if (not event.reply) or (not event.get_plaintext()):
            await cave_comment.finish()
        for msg in cave_messages:
            if msg["message_id"] == event.reply.message_id:
                cave_id = msg["cave_id"]
                break
        else:
            await cave_comment.finish()
        if str(event.user_id) in json.load(
            open("data/cave.banned.json", encoding="utf-8")
        ):
            await cave_comment.finish(
                _lang.text("cave.cannot_comment", [], str(event.user_id))
            )
        await showEula(event.get_user_id())
        auditdata = await context_review(event.get_plaintext(), "text", event.user_id)
        if auditdata["conclusionType"] == 2:
            reasons = [i["msg"] for i in auditdata["data"]]
            await cave_comment.finish(
                _lang.text(
                    "cave.audit_rejected", ["\n".join(reasons)], str(event.user_id)
                )
            )
        data = json.load(open("data/cave.comments.json", encoding="utf-8"))
        if cave_id not in data.keys():
            data[cave_id] = {"count": 1, "data": {}}
        data[cave_id]["data"][str(data[cave_id]["count"])] = {
            "id": data[cave_id]["count"],
            "text": str(event.get_plaintext()),
            "sender": event.get_user_id(),
        }
        data[cave_id]["count"] += 1
        json.dump(data, open("data/cave.comments.json", "w", encoding="utf-8"))
        await _error.report(
            f"「新回声洞评论（{cave_id}#{data[cave_id]['count'] - 1}）」\n{event.get_message()}\n{event.get_session_id()}"
        )
        exp.add_exp(event.get_user_id(), 2)
        await cave_comment.finish(f"评论成功：{cave_id}#{data[cave_id]['count'] - 1}")
    except BaseException:
        await _error.report(traceback.format_exc())


@app.get("/cave/data.json")
async def getCaveData():
    return json.load(open("data/cave.data.json", encoding="utf-8"))


async def downloadImages(message: str):
    cqStart = message.find("[CQ:image")
    # print("message", message)
    if cqStart == -1:
        return message
    else:
        url = message[message.find("url=", cqStart) + 4 : message.find("]", cqStart)]
        imageID = str(time.time())
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
        content = response.read()
        if not content:
            return False
        if (await context_review(url, "url"))["conclusionType"] == 2:
            return False
        with open(f"data/caveImages/{imageID}.png", "wb") as f:
            f.write(content)
        return await downloadImages(
            message.replace(
                message[cqStart : message.find("]", cqStart)], f"[[Img:{imageID}]]"
            )
        )


def parseCave(text: str):
    imageIDStart = text.find("[[Img:")
    if imageIDStart == -1:
        return text
    else:
        imageID = text[imageIDStart + 6 : text.find("]]]", imageIDStart)]
        imagePath = os.path.join(path, "data", "caveImages", f"{imageID}.png")
        imageCQ = f"[CQ:image,file=file://{imagePath}]"
        return parseCave(text.replace(f"[[Img:{imageID}]]]", str(imageCQ)))


@on_command("cave-g", permission=SUPERUSER).handle()
async def cave_get_handler(
    cave: Matcher, bot: Bot, event: GroupMessageEvent, message: Message = CommandArg()
):
    try:
        await showEula(event.get_user_id())

        argument = message.extract_plain_text().split(" ")
        data = json.load(open("data/cave.data.json", encoding="utf-8"))
        caveData = data["data"][argument[0]]
        text = parseCave(caveData["text"])

        if isinstance(caveData["sender"], dict):
            if caveData["sender"]["type"] == "nickname":
                senderData = {"nickname": caveData["sender"]["name"]}
            else:
                senderData = {"nickname": "未知"}
        else:
            senderData = await bot.get_stranger_info(user_id=caveData["sender"])
        await cave.send(
            Message(
                f"""{_lang.text("cave.name",[],event.get_user_id())}——（{caveData['id']}）\n{text}\n——{senderData['nickname']}"""
            )
        )
        comments = json.load(open("data/cave.comments.json", encoding="utf-8"))
        caveData["id"] = str(caveData["id"])
        if caveData["id"] in comments.keys():
            comments = list(comments[caveData["id"]]["data"].values())
            node_message = [[]]
            count = 0

            while len(comments) > 0:
                if count <= MAX_NODE_MESSAGE:
                    comment = comments.pop(-1)
                    node_message[-1].append(
                        {
                            "type": "node",
                            "data": {
                                "uin": comment["sender"],
                                "nickname": f"来自【{(await bot.get_stranger_info(user_id=comment['sender']))['nickname']}】的评论 - #{comment['id']}",
                                "content": comment["text"],
                            },
                        }
                    )
                else:
                    node_message.append([])
                    count = 0

            for node in node_message:
                await bot.call_api(
                    api="send_group_forward_msg",
                    messages=node,
                    group_id=event.get_session_id().split("_")[1],
                )
        await cave.finish()

    except KeyError as e:
        await cave.finish(_lang.text("cave.notfound", [e], event.get_user_id()))
    except:
        await _error.report()


@on_command("cave-q", permission=SUPERUSER).handle()
async def cave_query_handler(
    cave: Matcher, bot: Bot, event: GroupMessageEvent, message: Message = CommandArg()
):
    try:
        await showEula(event.get_user_id())

        argument = message.extract_plain_text().split(" ")
        data = json.load(open("data/cave.data.json", encoding="utf-8"))
        start_id = int(argument[0])
        end_id = int(argument[1])
        if end_id - start_id >= 175:
            await cave.finish(
                _lang.text("cave.query_too_many", [175], event.get_user_id())
            )
        node_message = []
        user_info = await bot.get_login_info()

        keys = data["data"].keys()
        for id in range(start_id, end_id):
            if str(id) in keys:
                caveData = data["data"][str(id)]

                text = parseCave(caveData["text"])
                if isinstance(caveData["sender"], dict):
                    if caveData["sender"]["type"] == "nickname":
                        senderData = {"nickname": caveData["sender"]["name"]}
                    else:
                        senderData = {"nickname": "未知"}
                else:
                    senderData = await bot.get_stranger_info(user_id=caveData["sender"])
                cave_text = (
                    f"{_lang.text('cave.name',[],event.get_user_id())}——（{caveData['id']}）\n"
                    f"{text}\n"
                    f"——{senderData['nickname']}\n"
                )

                node_message.append(
                    {
                        "type": "node",
                        "data": {
                            "uin": int(user_info["user_id"]),
                            "nickname": user_info["nickname"],
                            "content": cave_text,
                        },
                    }
                )
        await bot.call_api(
            api="send_group_forward_msg",
            messages=node_message,
            group_id=str(event.get_session_id().split("_")[1]),
        )
    except:
        await _error.report()


import re


def replace_text_with_regex(_text: str, regex: str, replace_to: str = "") -> str:
    """
    使用正则表达式替换文本

    Args:
        text (str): 源文本
        regex (str): 正则表达式
        replace_to (str): 替换的文本

    Returns:
        str: 替换后的文本
    """
    text = _text
    while result := re.search(regex, text):
        text = text.replace(result.group(0), replace_to)
    return text


import difflib


def check_text_similarity(text: str) -> tuple[dict, float] | None:
    """
    检查文本与回声洞内信息的相似度

    Args:
        text (str): 文本

    Returns:
        tuple[dict, float] | None: 可能一致的回声洞，为 None 则为查找失败。第一项为回声洞信息，第二项为相似度
    """
    if "[[Img:" in text:
        return None
    data = json.load(open("data/cave.data.json", encoding="utf-8"))
    for cave_info in list(data["data"].values()):
        if (
            similarity := difflib.SequenceMatcher(
                None,
                replace_text_with_regex(cave_info["text"], r"\[\[Img:[\.0-9]\]\]\]"),
                replace_text_with_regex(text, r"\[\[Img:[\.0-9]\]\]\]"),
            ).ratio()
        ) >= 0.75:
            return cave_info, similarity
    return None


BANNED_CQ_CODE: list[str] = [
    "[CQ:json",
    "[CQ:mface",
    "[CQ:xml",
    "[CQ:record",
    "[CQ:video",
    "[CQ:rps",
    "[CQ:dice",
    "[CQ:share",
    "[CQ:contact",
    "[CQ:location",
    "[CQ:forward",
]


class ForwardMessageParser:

    def __init__(self, bot: Bot, segment: MessageSegment) -> None:
        if segment.type != "forward":
            raise TypeError
        self.content = Message()
        self.bot = bot
        self.segment = segment

    async def parse(self) -> None:
        self.messages = await self.get_forward(self.segment)
        self.parse_message()

    def parse_message(self) -> None:
        message_length = len(self.messages)
        if message_length <= 0:
            raise ValueError
        elif message_length == 1:
            self.content = self.messages[0][1]
        elif message_length > 1 and all(
            message[0] == self.messages[0][0] for message in self.messages
        ):
            self.merge_messages()
        else:
            raise ValueError

    def merge_messages(self) -> None:
        for _, message in self.messages:
            self.content += message

    async def get_forward(self, segment: MessageSegment) -> list[tuple[int, Message]]:
        response = cast(
            dict[str, dict], await self.bot.get_forward_msg(id=segment.data["id"])
        )
        messages = []
        for message_data in response["messages"]:
            message = Message([MessageSegment(**s) for s in message_data["message"]])
            if any(keyword in str(message) for keyword in BANNED_CQ_CODE):
                raise ValueError
            messages.append((message_data["sender"]["user_id"], message))
        return messages


@on_command("cave-a").handle()
async def cave_add_handler(
    cave: Matcher, bot: Bot, event: MessageEvent, argument: Message = CommandArg()
):
    global cave_confirm
    try:
        if (
            (not argument)
            and event.reply
            and all(
                [
                    keyword not in str(event.reply.message)
                    for keyword in BANNED_CQ_CODE[:-1]
                ]
            )
        ):
            message = event.reply.message
            if str(message).startswith("[CQ:forward"):
                parser = ForwardMessageParser(bot, message[0])
                try:
                    await parser.parse()
                except ValueError:
                    message = argument
                else:
                    message = parser.content

        else:
            message = argument
        await showEula(event.get_user_id())

        data = json.load(open("data/cave.data.json", encoding="utf-8"))
        if str(event.user_id) in json.load(
            open("data/cave.banned.json", encoding="utf-8")
        ):
            await cave.finish(_lang.text("cave.cannot_add", [], str(event.user_id)))
        text = await downloadImages(str(message).strip())

        if text == "":
            await cave.finish(
                _lang.text("cave.not_allow_null_cave", [], event.get_user_id())
            )
        elif not text:
            await cave.finish(
                _lang.text("cave.error_to_download_images", [], event.get_user_id())
            )
        elif (
            re.fullmatch(r"(\[\[Img:\d+\.\d+\]\]\])+", text) is None
            and (auditdata := await context_review(text, "text", event.user_id))[
                "conclusionType"
            ]
            == 2
        ):
            reasons = [i["msg"] for i in auditdata["data"]]
            await cave.finish(
                _lang.text(
                    "cave.audit_rejected", ["\n".join(reasons)], str(event.user_id)
                )
            )
        elif similarity_check_status := check_text_similarity(text):
            cave_data = similarity_check_status[0]
            if isinstance(cave_data["sender"], dict):
                if cave_data["sender"]["type"] == "nickname":
                    senderData = {"nickname": cave_data["sender"]["name"]}
                else:
                    senderData = {"nickname": "未知"}
            else:
                senderData = await bot.get_stranger_info(user_id=cave_data["sender"])
            confirm_message_id = (
                await cave.send(
                    Message(
                        _lang.text(
                            "cave.cave_has_been_here",
                            [
                                cave_data["id"],
                                round(similarity_check_status[1] * 100, 3),
                                parseCave(cave_data["text"]),
                                senderData["nickname"],
                            ],
                            event.get_user_id(),
                        )
                    )
                )
            )["message_id"]
            cave_confirm[confirm_message_id] = {
                "id": data["count"],
                "text": text,
                "sender": event.get_user_id(),
                "time": time.time(),
            }
            await asyncio.sleep(10)
            del cave_confirm[confirm_message_id]
            await cave.finish()

        data["data"][data["count"]] = {
            "id": data["count"],
            "text": text,
            "sender": event.get_user_id(),
            "time": time.time(),
        }
        data["count"] += 1
        exp.add_exp(event.get_user_id(), 5)

        # 发送通知
        await _error.report(
            (
                f"{_lang.text('cave.new',[data['count']-1])}"
                f"{event.get_session_id()}\n \n"
                f"{str(message).strip()}"
            )
        )

        cave_messages.append(
            {"message_id": event.message_id, "cave_id": data["count"] - 1}
        )
        if len(cave_messages) >= 10:
            cave_messages.pop(0)

        # 写入数据
        json.dump(data, open("data/cave.data.json", "w", encoding="utf-8"))
        await cave.finish(
            _lang.text("cave.added", [data["count"] - 1], event.get_user_id())
        )
    except:
        await _error.report()


@cave_confirm_add.handle()
async def _(event: MessageEvent, bot: Bot):
    global cave_confirm
    try:
        if not event.reply:
            await cave_confirm_add.finish()
        if not event.reply.message_id in cave_confirm:
            await cave_confirm_add.finish()
        cave_data = cave_confirm[event.reply.message_id]
        if (user_id := event.get_user_id()) != cave_data["sender"]:
            await cave_confirm_add.finish()
        data = json.load(open("data/cave.data.json", encoding="utf-8"))
        data["data"][data["count"]] = cave_data
        data["count"] += 1
        exp.add_exp(user_id, 5)

        await _error.report(
            (
                f"{_lang.text('cave.new', [data['count'] - 1])}"
                f"{event.get_session_id()}\n \n"
                f"{cave_data['text']}"
            )
        )

        json.dump(data, open("data/cave.data.json", "w", encoding="utf-8"))
        await cave_confirm_add.finish(
            _lang.text("cave.added", [data["count"] - 1], user_id)
        )
    except:
        await _error.report()


@on_command("cave-s").handle()
async def cave_status_handler(cave: Matcher, event: GroupMessageEvent):
    try:
        await showEula(event.get_user_id())

        data = json.load(open("data/cave.data.json", encoding="utf-8"))
        count = data["count"]
        canReadCount = len(data["data"].keys())
        await cave.finish(
            _lang.text(
                "cave.data_finish",
                [count, canReadCount, len(os.listdir("data/caveImages"))],
                event.get_user_id(),
            )
        )
    except:
        await _error.report()


def get_cd_time(group_id: int) -> int:
    data = Json("cave.cd_time.json")
    data.update({"468502962": 2400, "701257458": 2400, "159910125": 1200})
    return data.get(str(group_id), 3600)


@on_command("cave").handle()
async def cave_handler(cave: Matcher, bot: Bot, event: GroupMessageEvent):
    try:
        await showEula(event.get_user_id())

        data = json.load(open("data/cave.data.json", encoding="utf-8"))
        latest_use = json.load(open("data/cave.latest_use.json", encoding="utf-8"))
        cd_time = get_cd_time(event.group_id)

        if time.time() - latest_use.get(f"u{event.user_id}", 0) < 600:
            await finish(
                "cave.user_cd",
                [
                    round(
                        (600 - (time.time() - latest_use.get(f"u{event.user_id}", 0)))
                        / 60,
                        3,
                    )
                ],
                event.user_id,
                True,
                False,
            )
        if time.time() - (latest_use.get(f"g{event.group_id}") or 0) < cd_time:
            await cave.finish(
                _lang.text(
                    "cave.cd",
                    [
                        str(
                            round(
                                (
                                    cd_time
                                    - (time.time() - latest_use[f"g{event.group_id}"])
                                )
                                / 60,
                                3,
                            )
                        )
                    ],
                    event.get_user_id(),
                ),
                at_sender=True,
            )

        caveList = data["data"].values()
        random.seed(marshal.loads(b"\xe9" + os.urandom(4)))
        caveData = random.choice(list(caveList))
        text = parseCave(caveData["text"])
        if isinstance(caveData["sender"], dict):
            if caveData["sender"]["type"] == "nickname":
                senderData = {"nickname": caveData["sender"]["name"]}
            else:
                senderData = {"nickname": "未知"}
        else:
            senderData = await bot.get_stranger_info(user_id=caveData["sender"])
        message_id = (
            await bot.send_group_msg(
                message=Message(
                    (
                        f'{_lang.text("cave.name",[],event.get_user_id())}——（{caveData["id"]}）\n'
                        f"{text}\n"
                        f"——{senderData['nickname']}"
                    )
                ),
                group_id=event.group_id,
            )
        )["message_id"]
        cave_messages.append({"message_id": message_id, "cave_id": caveData["id"]})
        if len(cave_messages) >= 10:
            cave_messages.pop(0)
        latest_use[f"g{event.group_id}"] = time.time()
        latest_use[f"u{event.user_id}"] = time.time()
        json.dump(latest_use, open("data/cave.latest_use.json", "w", encoding="utf-8"))
        if random.random() <= 0.25:
            economy.add_vi(str(event.user_id), t := random.randint(1, 10))
            await cave.send(_lang.text("cave.getvim", [t], event.user_id))
        # 发送评论
        comments = json.load(open("data/cave.comments.json", encoding="utf-8"))
        caveData["id"] = str(caveData["id"])
        if caveData["id"] in comments.keys():
            comments = list(comments[caveData["id"]]["data"].values())
            node_message = [[]]
            count = 0

            while len(comments) > 0:
                if count <= MAX_NODE_MESSAGE:
                    comment = comments.pop(0)
                    node_message[-1].append(
                        {
                            "type": "node",
                            "data": {
                                "uin": comment["sender"],
                                "nickname": f"来自【{(await bot.get_stranger_info(user_id=comment['sender']))['nickname']}】的评论 - #{comment['id']}",
                                "content": comment["text"],
                            },
                        }
                    )
                else:
                    node_message.append([])
                    count = 0

            for node in node_message:
                await bot.call_api(
                    api="send_group_forward_msg",
                    messages=node,
                    group_id=event.get_session_id().split("_")[1],
                )
        await cave.finish()
    except Exception:
        await _error.report(traceback.format_exc(), cave)
