from typing import Awaitable
from ._utils import *

generators = []


def registry(func: Callable[[str], Awaitable[str]]) -> None:
    generators.append(func)


from datetime import datetime


def format_week() -> str:
    return datetime.now().strftime("%yw%Ua")


@create_command("weekly")
async def _(bot: Bot, event: MessageEvent, message: Message) -> None:
    messages = [lang.text("weekly.title", [format_week()], event.user_id)]
    for generator in generators:
        messages.append(await generator(event.get_user_id()))
    await send_node_message(bot, await generate_node_message(bot, messages), event)
    await finish(get_currency_key("ok"), [], event.user_id)


# @registry
# async def _(_user: str) -> str:
#     last = Json("weekly.last.json")
#     data = Json("_error.count.json")
#     e = last["error"]
#     last["error"] = data["count"]
#     return lang.text(
#         "weekly.error",
#         [
#             data["count"] - e,
#             round((data["count"] - e) / e * 100)
#         ],
#         _user
#     )
