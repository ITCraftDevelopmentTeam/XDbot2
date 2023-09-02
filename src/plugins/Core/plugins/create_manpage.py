# [DEVELOP]
from ._utils import *
import subprocess
import os
from .chatgptv2 import get_chatgpt_reply


async def get_command_help(command_name: str, user_id: int) -> dict | None:
    if (data := Json("help.json")[command_name]) is not None:
        return data
    await finish("create_manpage.404", [], user_id, False, True)


def generate_prompt(command_help: dict) -> str:
    prompt = (
        "请参考以下信息，写一个指令文档，允许使用部分 markdown 语法，说明尽量简短，Reply me in Chinese\n\n"
        f"Command: {command_help['name']}\n"
        f"Info: {command_help['info']}\n"
        "Usage:"
    )
    for usage in command_help["usage"]:
        prompt += f"- {usage}"
    return prompt


def push_changes(command_name) -> str:
    subprocess.Popen(["git", "add", "-A"], shell=True).communicate()
    subprocess.Popen(
        ["git", "commit", "-m", f"[add] Create manpage for {command_name}"],
        shell=True).communicate()
    subprocess.Popen(["git", "pull"], shell=True).communicate()
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