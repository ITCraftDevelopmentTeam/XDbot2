from .etm import bag
from ._utils import *
from .etm import exp, json2items
from .etm.item import Item
import os
import math


def get_item_list() -> list:
    file_list = os.listdir("src/plugins/Core/synthesis/")
    item_list = []
    for file in file_list:
        if (not file.startswith("_")) and file.endswith(".json"):
            item_list.append(
                Json(os.path.join("../src/plugins/Core/synthesis/", file)).to_dict()
            )
    return sorted(item_list, key=lambda x: x["id"])


def items2text(item_list: list[Item]) -> str:
    text = ""
    length = 0
    for item in item_list:
        length += 1
        text += f"\n {length}. {item.data['display_name']} x{item.count}"
    return text[1:]


def list_items(page: int, self_id: int, user_id: int) -> list[dict]:
    item_list = get_item_list()
    node_messages = [
        {
            "type": "node",
            "data": {
                "uin": self_id,
                "nickname": "XDbot2",
                "content": lang.text(
                    "synthesis.list_title",
                    [page, math.ceil(len(item_list) / 100)],
                    user_id,
                ),
            },
        }
    ]

    for item_data in item_list[100 * (page - 1) : 100 * page]:
        result_items = json2items.json2items(item_data["result"])
        required_items = json2items.json2items(item_data["required"])
        node_messages.append(
            {
                "type": "node",
                "data": {
                    "uin": self_id,
                    "nickname": "XDbot2",
                    "content": lang.text(
                        "synthesis.list_item",
                        [
                            str(item_data["id"]),
                            items2text(result_items),
                            items2text(required_items),
                        ],
                        user_id,
                    ),
                },
            }
        )
    return node_messages


def get_page(argv: list):
    try:
        return int(argv[1])
    except:
        return 1


SYNTHESIS_CONSUMES_PAWCOIN = 1


def get_item(_id: int) -> dict | None:
    for item in get_item_list():
        if item["id"] == _id:
            return item
    return None


def get_required_items(item_data: dict, count: int) -> dict:
    required_items = {}
    for item in item_data["required"]:
        required_items[item["id"]] = (
            required_items.get(item["id"], 0) + item["count"] * count
        )
    required_items["pawcoin"] = (
        required_items.get("pawcoin", 0) + SYNTHESIS_CONSUMES_PAWCOIN * count
    )
    return required_items


def check_required_items(_required_items: dict[str, int], user_id: str):
    required_items = _required_items.copy()
    for item in bag.get_user_bag(user_id):
        if item.item_id in required_items.keys() and not item.data.get("locked", False):
            required_items[item.item_id] -= item.count
            if required_items[item.item_id] <= 0:
                required_items.pop(item.item_id)
    return len(list(required_items.keys())) == 0


async def send_crafting_result(item_data: dict, count: int, user_id: str):
    reduced_items = []
    for item_id, c in list(get_required_items(item_data, count).items()):
        reduced_items.append({"id": item_id, "count": c, "data": {}})
    for i in range(len(item_data["result"])):
        item_data["result"][i]["count"] *= count
    await finish(
        "synthesis.done",
        [
            items2text(json2items.json2items(reduced_items)),
            items2text(json2items.json2items(item_data["result"])),
        ],
        user_id,
    )


async def crafting_items(_id: int, count: int, user_id: str):
    if (item_data := get_item(_id)) is None:
        await finish("synthesis.item_not_found", [], user_id, False, True)
    required_items = get_required_items(item_data, count)  # type: ignore
    if check_required_items(required_items, user_id):
        user_bag = bag.get_user_bag(user_id)
        for i in range(len(user_bag)):
            if user_bag[i].item_id in required_items.keys():
                user_bag[i]._used(
                    reduced_count := min(
                        user_bag[i].count, required_items[user_bag[i].item_id]
                    )
                )
                required_items[user_bag[i].item_id] -= reduced_count
        for item in item_data["result"]:
            bag.add_item(user_id, item["id"], item["count"] * count, item["data"])
        exp.add_exp(user_id, int(5.2 * count))
        await send_crafting_result(item_data, count, user_id)
    else:
        await finish("synthesis.item_not_enough", [], user_id, False, True)


@on_command("synthesis", aliases={"合成"}).handle()
async def handle_synthesis_command(
    bot: Bot, event: MessageEvent, message: Message = CommandArg()
):
    try:
        argv = message.extract_plain_text().split(" ")
        match argv[0]:
            case "" | "list":
                await bot.call_api(
                    f"send_{'group' if event.get_session_id().split('_')[0]  == 'group' else 'private'}_forward_msg",
                    messages=list_items(get_page(argv), event.self_id, event.user_id),
                    user_id=int(event.get_user_id()),
                    group_id=event.dict().get("group_id"),
                )
            case _:
                try:
                    count = max(int(argv[1]), 1)
                except Exception:
                    count = 1
                await crafting_items(int(argv[0]), count, event.user_id)
    except:
        await error.report()


# [HELPSTART] Version: 2
# Command: synthesis
# Info: 万能（并不）合成机
# Msg: 万能合成机
# Usage: synthesis list [页面]：查看配方列表
# Usage: synthesis <配方ID> [数量]：合成物品
# [HELPEND]
