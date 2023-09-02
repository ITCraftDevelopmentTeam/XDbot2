# [DEVELOP]
from ._utils import *
import os
from .chatgptv2 import get_chatgpt_reply


async def get_command_help(command_name: str, user_id: int) -> dict | None:
    if (data := Json("help.json")[command_name]) is not None:
        return data
    await finish("create_manpage.404", [], user_id, False, True)


def generate_prompt(command_help: dict) -> str:
    prompt = (
        "请参考以下指令帮助，写一个类似 Manpage 的指令文档，需要包含名称、描述、权限、用法、示例等信息，允许使用 markdown（但不能使用代码块），内容尽量详细，Reply me in Chinese\n\n"
        f"命令名：{command_help['name']}\n"
        f"简介（[...]内为权限，以*开头（需要去掉*），使用空格分割，没有则为 *everyone）：{command_help['info']}\n"
        "所有用法（<...>为必要参数，[...]为可选参数，{...|...}为选择参数）："
    )
    for usage in command_help["usage"]:
        prompt += f"- {usage}"
    return prompt


def push_changes(command_name) -> str:
    os.system("git add -A")
    os.system(f"git commit -a -m \"[add] Create manpage for {command_name}\"")
    return os.popen("git push").read()


@create_command("create-manpage")
async def create_manpage(_bot: Bot, event: MessageEvent, message: Message, matcher: Matcher = Matcher()):
    session = await get_chatgpt_reply([{
        "role": "user",
        "content": generate_prompt(await get_command_help(message.extract_plain_text(), event.user_id))
    }])
    await matcher.send(session["choices"][0]["message"]["content"])
    try:
        os.mkdir(f"docs/{message.extract_plain_text()}")
    except OSError:
        pass
    with open(path := f"docs/{message.extract_plain_text()}/0.md", "w", encoding="utf-8") as f:
        f.write(session["choices"][0]["message"]["content"])
    await send_text("create_manpage.saved", [path], event.user_id)
    await matcher.send(push_changes(message.extract_plain_text()))
