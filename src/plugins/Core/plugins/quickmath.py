from io import BytesIO
import time
from ._utils import *
import json
import random
from sympy import Symbol, Eq, solve, latex
from nonebot_plugin_apscheduler import scheduler
from nonebot import get_bot, on_fullmatch, require
from PIL import Image, ImageDraw, ImageFont
from nonebot.adapters.onebot.v11.message import MessageSegment
import asyncio


require("nonebot_plugin_apscheduler")


def render_question(question_string: str) -> bytes:
    title_font = ImageFont.truetype("./src/plugins/Core/font/HYRunYuan-55W.ttf", 17)
    question_font = ImageFont.truetype("./src/plugins/Core/font/HYRunYuan-55W.ttf", 20)

    width1 = question_font.getlength(question_string)
    width2 = question_font.getlength("[QUICK MATH]")
    height1 = 17
    height2 = 20

    image = Image.new("RGB", (int(max(width1, width2)), 40), color="white")
    draw = ImageDraw.Draw(image)
    draw.text((0, 18), question_string, fill="black", font=question_font)
    draw.text((0, 0), "[QUICK MATH]", fill="black", font=title_font)
    bbox = image.getbbox()
    image = image.crop(bbox)
    io = BytesIO()
    image.save(io, format="PNG")
    return io.getvalue()


def get_group() -> int:
    try:
        return random.choice(
            json.load(open("data/quick_math.enabled_groups.json", encoding="utf-8"))
        )
    except BaseException:
        return 0


3


def check_group(group_id: int) -> bool:
    return bool(
        group_id and Json("quickmath/group_unanswered.json").get(str(group_id), 0) <= 3
    )


def generate_question() -> tuple:
    if random.random() <= 0.5:
        question = (
            f"{random.randint(0, 50)}{random.choice('+-*')}{random.randint(1, 50)}"
        )
        answer = [str(eval(question))]
        question += "=?"
    else:
        x = Symbol("x")
        a, b = random.randint(1, 10), random.randint(1, 10)
        eq = Eq(a * x + b, random.randint(1, 50))  # type: ignore
        ans = solve(eq)
        question = latex(eq).replace(" ", "")
        answer = [(tmp := str(ans).replace("[", "").replace("]", "")), str(eval(tmp))]
    return question, answer


@scheduler.scheduled_job("cron", minute="*/2", id="send_quick_math")
async def send_quick_math() -> None:
    if not check_group(group := get_group()):
        return
    question, answer = generate_question()
    bot = get_bot(Json("su.multiaccoutdata.ro.json")[str(group)])
    msg_id = (
        await bot.send_group_msg(
            group_id=group, message=[MessageSegment.image(render_question(question))]
        )
    )["message_id"]
    matcher = on_fullmatch(tuple(answer))
    send_time = time.time()
    answered = False

    @matcher.handle()
    async def handle_quickmath_answer(event: GroupMessageEvent) -> None:
        nonlocal answered
        try:
            if event.group_id != group:
                await matcher.finish()
            answered = True
            await send_text(
                "quick_math.rightanswer1",
                [(add_points := int(2 * (20 - time.time() + send_time)))],
                event.user_id,
                False,
                True,
            )
            try:
                matcher.destroy()
            except ValueError:
                pass
            Json(f"quickmath/u{event.user_id}.json")["points"] = (
                Json(f"quickmath/u{event.user_id}.json").get("points", 0) + add_points
            )
            Json("quickmath/group_unanswered.json")[str(event.group_id)] = 0
            Json(f"quickmath/global.json")["count"] = (
                Json(f"quickmath/global.json").get("count", 0) + 1
            )
        except:
            await error.report()

    await asyncio.sleep(20)
    if not answered:
        try:
            matcher.destroy()
        except ValueError:
            return
        await bot.delete_msg(message_id=msg_id)
        Json("quickmath/group_unanswered.json")[str(group)] = (
            Json("quickmath/group_unanswered.json").get(str(group), 0) + 1
        )


@on_command("quick-math", aliases={"qm"}).handle()
async def quick_math_command(
    matcher: Matcher, event: GroupMessageEvent, message: Message = CommandArg()
) -> None:
    try:
        groups = json.load(
            open("data/quick_math.enabled_groups.json", encoding="utf-8")
        )
        if str(message) in ["on", "enable", "开启", "启用"]:
            if event.group_id not in groups:
                groups.append(event.group_id)
            await matcher.send(lang.text("quick_math.enable", [], event.get_user_id()))
        elif str(message) in ["off", "disable", "关闭", "禁用"]:
            try:
                groups.pop(groups.index(event.group_id))
            except IndexError:
                pass
            await matcher.send(lang.text("quick_math.disable", [], event.get_user_id()))
        else:
            if event.group_id in groups:
                groups.pop(groups.index(event.group_id))
                await matcher.send(
                    lang.text("quick_math.disable", [], event.get_user_id())
                )
            else:
                groups.append(event.group_id)
                await matcher.send(
                    lang.text("quick_math.enable", [], event.get_user_id())
                )
        json.dump(
            groups, open("data/quick_math.enabled_groups.json", "w", encoding="utf-8")
        )
    except BaseException:
        await error.report()


@on_message().handle()
async def reset_group_unanswered(event: GroupMessageEvent) -> None:
    if Json("quickmath/group_unanswered.json").get(
        f"{event.group_id}", 0
    ) >= 3 and event.user_id not in [2920571540, 1552257261]:
        Json("quickmath/group_unanswered.json")[f"{event.group_id}"] = int(
            random.choice("011222")
        )


# [HELPSTART] Version: 2
# Command: quick-math
# Usage: qm {on|off}：开启/关闭速算
# Usage: qm-p：查看速算积分排行
# Info: 速算
# Msg: 速算
# [HELPEND]
