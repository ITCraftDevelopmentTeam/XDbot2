import os.path
import random
from nonebot.params import ArgPlainText
from nonebot.typing import T_State
import re
import difflib
import os.path
from nonebot import on_message
from ._utils import *
import math

sent_messages = []


def get_rules(group_id: int):
    try:
        file_list = os.listdir(f"data/reply/g{group_id}/")
        rule_list = []
        for file in file_list:
            rule_list.append(file[:-5])
        return rule_list
    except OSError:
        return []


def get_rule_data(group_id: int, rule_id: str):
    return Json(f"reply/g{group_id}/{rule_id}.json").to_dict()


def is_matched_rule(rule_id: str, group_id: int, message: str):
    try:
        data = Json(f"reply/g{group_id}/{rule_id}.json")["match"]
        match data["type"]:
            case "regex":
                return bool(re.match(re.compile(data["text"], re.DOTALL), message))
            case "keyword":
                return data["text"] in message
            case "fullmatch":
                return data["text"] == message
            case "fuzzymatch":
                return (
                    difflib.SequenceMatcher(None, data["text"], message).ratio() >= 0.75
                )
    except:
        pass


def get_rule_reply(rule_id: str, group_id: int):
    return random.choice(Json(f"reply/g{group_id}/{rule_id}.json")["reply"])


# [HELPSTART] Version: 2
# Command: reply
# Usage: reply add {regex|keyword|fullmatch|fuzzymatch}\n[匹配内容]：添加匹配规则
# Usage: reply show <数据编号>：查看调教数据
# Usage: reply source：（需回复）获取回复来源
# Usage: reply remove <数据编号>：删除数据
# Usage: reply list：查看数据列表
# Usage: reply fork <群号> <数据编号>：复刻调教数据
# Msg: 调教模块
# Info: 调教XDbot2，支持正则、关键词、完整、模糊四种匹配模式
# [HELPEND]


@on_message().handle()
async def match_rules(bot: Bot, event: GroupMessageEvent):
    global sent_messages
    message = str(event.get_message())
    if random.random() > Json("reply/config/group_probability.json").get(
        "group_id", 1
    ) or random.random() > Json("reply/config/probability.json").get(
        event.get_user_id(), 1
    ):
        return
    for rule_id in get_rules(event.group_id):
        if is_matched_rule(rule_id, event.group_id, message):
            sent_messages.append(
                {
                    "message_id": (
                        await bot.send_group_msg(
                            message=Message(get_rule_reply(rule_id, event.group_id)),
                            group_id=event.group_id,
                        )
                    )["message_id"],
                    "from_id": f"{rule_id}",
                }
            )
            sent_messages = sent_messages[-20:]


def get_matcher_type(argv: str):
    reply_matcher_types = [
        ["regex", "re", "正则", "正则表达式"],
        ["keyword", "kwd", "关键词"],
        ["fullmatch", "full", "完全匹配"],
        ["fuzzymatch", "fuzzy", "模糊匹配"],
    ]
    for _type in reply_matcher_types:
        if argv in _type:
            return _type[0]


def fork_reply_data(base_data: dict, group_id: int) -> int:
    """复刻调教数据

    Args:
        base_data (dict): 源调教数据
        group_id (int): 目标群聊

    Returns:
        int: 新的数据编号
    """
    base_data["id"] = get_reply_id(group_id)
    base_data["group_id"] = group_id
    Json(f"reply/g{group_id}/{base_data['id']}.json").update(base_data)
    return base_data["id"]


def get_reply_id(group_id: int):
    length = 0
    while True:
        if not os.path.isfile(f"data/reply/g{group_id}/{length}.json"):
            return length
        else:
            length += 1


def remove_matcher(group_id: int, rule_id: str, user_id: str, force: bool = False):
    if get_rule_data(group_id, rule_id)["user_id"] == user_id or force:
        os.remove(f"data/reply/g{group_id}/{rule_id}.json")
        return SUCCESS
    else:
        return FAILED


def is_rule_id_available(group_id: int, rule_id: str) -> bool:
    """
    检查数据编号是否有效

    Args:
        group_id (int): 群号
        rule_id (str): 数据编号

    Returns:
        bool: 数据编号是否有效
    """
    return os.path.isfile(f"data/reply/g{group_id}/{rule_id}.json")


async def create_matcher(
    user_id: str,
    group_id: int,
    matcher_type: str,
    matcher_data: str,
    reply_text: list[str],
):
    reply_id = get_reply_id(group_id)
    Json(f"reply/g{group_id}/{reply_id}.json").update(
        {
            "id": reply_id,
            "match": {"type": matcher_type, "text": matcher_data},
            "reply": reply_text,
            "group_id": group_id,
            "user_id": user_id,
        }
    )
    await error.report(
        (
            f"「新调教数据投稿（#{reply_id}）」\n"
            f"群聊：{group_id}\n"
            f"触发器类型：{matcher_type}\n"
            f"触发文本：{matcher_data}\n"
            f"回复文本：{reply_text}"
        ),
        feedback=False,
    )
    return reply_id


reply_command = on_command("reply", aliases={"调教"})


@reply_command.handle()
async def handle_reply(
    state: T_State,
    matcher: Matcher,
    bot: Bot,
    event: GroupMessageEvent,
    message: Message = CommandArg(),
):
    try:
        try:
            argv = message.extract_plain_text().splitlines()[0].split(" ")
        except IndexError:
            argv = message.extract_plain_text().split(" ")

        if argv[0] in ["add", "添加"]:
            state["matcher_type"] = get_matcher_type(argv[1])
            if len(message.extract_plain_text().splitlines()) > 1:
                matcher.set_arg(
                    "match_text",
                    Message("\n".join(message.extract_plain_text().splitlines()[1:])),
                )
            else:
                await send_text("reply.add_match_text", [], event.user_id)

        elif argv[0] in ["get-source", "获取来源", "source", "来源"]:
            for msg in sent_messages:
                if msg["message_id"] == event.reply.message_id:
                    await finish(
                        "reply.getsource",
                        [
                            msg["from_id"],
                            get_rule_data(event.group_id, msg["from_id"])["user_id"],
                        ],
                        event.user_id,
                        False,
                        True,
                    )

        elif argv[0] in ["remove", "delete", "删除"]:
            if remove_matcher(event.group_id, argv[1], event.get_user_id()):
                await finish("currency.ok", [], event.user_id)
            else:
                await finish("reply.403", [], event.user_id)

        elif argv[0] in ["show", "view", "查看"]:
            await finish(
                "reply.show_data",
                [
                    argv[1],
                    (data := get_rule_data(event.group_id, argv[1]))["user_id"],
                    data["match"]["type"],
                    data["match"]["text"],
                    "\n· " + "\n· ".join(data["reply"]),
                ],
                event.user_id,
                False,
                True,
            )

        elif argv[0] in ["list", "all", "列表", "查看全部", ""]:
            try:
                node_messages = [
                    {
                        "type": "node",
                        "data": {
                            "uin": event.self_id,
                            "nickname": "XDbot2 Smart Reply",
                            "content": lang.text(
                                "reply.list_title",
                                [
                                    (page := int(argv[1]) if len(argv) >= 2 else 1),
                                    math.ceil(
                                        len(rule_list := get_rules(event.group_id))
                                        / 100
                                    ),
                                ],
                                event.user_id,
                            ),
                        },
                    }
                ]
            except ValueError:
                await finish(
                    "currency.wrong_argv", ["reply"], event.user_id, False, True
                )
            for rule_id in rule_list[(page - 1) * 100 : page * 100]:
                rule_id = rule_id.replace(".json", "")
                node_messages.append(
                    {
                        "type": "node",
                        "data": {
                            "uin": event.self_id,
                            "nickname": "XDbot2 Smart Reply",
                            "content": lang.text(
                                "reply.show_data",
                                [
                                    rule_id,
                                    (data := get_rule_data(event.group_id, rule_id))[
                                        "user_id"
                                    ],
                                    data["match"]["type"],
                                    data["match"]["text"],
                                    "\n· " + "\n· ".join(data["reply"]),
                                ],
                                event.user_id,
                            ),
                        },
                    }
                )
            await bot.call_api(
                "send_group_forward_msg",
                group_id=event.group_id,
                messages=node_messages,
            )
            await reply_command.finish()

        elif argv[0] in ["fork", "copy", "复刻"]:
            if not is_rule_id_available(int(argv[1]), argv[2]):
                await finish("reply.not_found", [], event.user_id)
            await finish(
                "reply.fork_successful",
                [fork_reply_data(get_rule_data(int(argv[1]), argv[2]), event.group_id)],
                event.user_id,
            )

        elif argv[0] in ["clone", "克隆"]:
            for rule_id in get_rules(group_id := int(argv[1])):
                rule: dict = get_rule_data(group_id, rule_id)
                print(rule_id, group_id, rule)
                await create_matcher(
                    event.get_user_id(),
                    event.group_id,
                    rule["match"]["type"],
                    rule["match"]["text"],
                    rule["reply"],
                )
            await finish(
                "reply.clone_successful", [len(get_rules(int(argv[1])))], event.user_id
            )

        else:
            await finish("reply.need_argv", [], event.user_id)
        # await reply_command.finish()

    except:
        await error.report()
        await reply_command.finish()


@reply_command.got("match_text")
async def receive_matchtext(
    state: T_State, event: GroupMessageEvent, match_text: str = ArgPlainText()
):
    try:
        if match_text in ["cancel", "取消"]:
            await finish("reply.canceled", [], event.user_id)
        state["match_text"] = match_text
        state["_reply_text"] = []
        await send_text("reply.add_reply_text", [], event.user_id)
    except:
        await error.report()


@reply_command.got("reply_text")
async def receive_replytext(
    state: T_State, event: GroupMessageEvent, reply_text: str = ArgPlainText()
):
    if reply_text in ["cancel", "取消"]:
        await finish("reply.canceled", [], event.user_id)
    if reply_text in ["finish", "ok", "完成"]:
        await finish(
            "reply.done",
            [
                await create_matcher(
                    event.get_user_id(),
                    event.group_id,
                    state["matcher_type"],
                    state["match_text"],
                    state["_reply_text"],
                )
            ],
            event.user_id,
        )
    state["_reply_text"].append(reply_text)
    await reply_command.reject(lang.text("reply.reject", [], event.user_id))
