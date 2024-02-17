import asyncio
from ._utils import *
from src.plugins.Core.lib.FindingTheTrail import search, const, image, map, argv
from nonebot.params import ArgPlainText
from nonebot.typing import T_State
import copy
import asyncio

import multiprocessing

ftt = on_command("ftt", aliases={"FindingTheTrail"})


def generate_map(difficulty: str) -> tuple[list[list[int]], list[int]]:
    while True:
        game_map = map.generate(**argv.ARGUMENTS[difficulty]["map"])
        answer = search.search(
            copy.deepcopy(game_map), **argv.ARGUMENTS[difficulty]["search"]
        )
        if len(answer) < argv.ARGUMENTS[difficulty]["min_step"]:
            continue
        break
    return game_map, answer


def createMapCache() -> None:
    cache = Json(f"ftt.cache.json")
    for d in argv.ARGUMENTS.keys():
        for _ in range(5 - len(cache.get(d, []))):
            gameMap, answer = generate_map(d)
            cache.append_to({"map": gameMap, "answer": answer}, d)
    logger.info("Done")


cacheCreateProcess = multiprocessing.Process(target=createMapCache)
cacheCreateProcess.start()


async def getGameMap(difficulty: str) -> tuple[list[list[int]], list[int]]:
    cache = Json(f"ftt.cache.json")
    if cache[difficulty]:
        data = cache[difficulty].pop(0)
        cache.changed_key.add(difficulty)
        logger.info("[FTT] 使用缓存 ...")
        return data["map"], data["answer"]
    else:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, generate_map, difficulty)


@ftt.handle()
async def _(
    state: T_State, bot: Bot, event: MessageEvent, message: Message = CommandArg()
) -> None:
    global cacheCreateProcess
    try:
        difficulty = message.extract_plain_text().strip() or "easy"
        message_id = await send_message(bot, event, "ftt.generating_map")
        state["map"], state["answer"] = await getGameMap(difficulty)
        await bot.delete_msg(message_id=message_id)
        await send_text(
            "ftt.map",
            [
                MessageSegment.image(image.generate(state["map"])),
                0,
                len(state["answer"]),
            ],
            event.user_id,
        )
        state["_steps"] = []
        if not cacheCreateProcess.is_alive():
            cacheCreateProcess = multiprocessing.Process(target=createMapCache)
            cacheCreateProcess.start()
    except Exception:
        await error.report()


async def handle_steps(state: T_State, steps: str, user_id: int) -> Optional[str]:
    match steps.lower().strip():
        case "w":
            state["_steps"].append(const.UP)
            return lang.text(
                "ftt.step_nb",
                [len(state["_steps"]), lang.text("ftt.step_up_nb", [], user_id)],
                user_id,
            )
        case "s":
            state["_steps"].append(const.DOWN)
            return lang.text(
                "ftt.step_nb",
                [len(state["_steps"]), lang.text("ftt.step_down_nb", [], user_id)],
                user_id,
            )
        case "a":
            state["_steps"].append(const.LEFT)
            return lang.text(
                "ftt.step_nb",
                [len(state["_steps"]), lang.text("ftt.step_left_nb", [], user_id)],
                user_id,
            )
        case "d":
            state["_steps"].append(const.RIGHT)
            return lang.text(
                "ftt.step_nb",
                [len(state["_steps"]), lang.text("ftt.step_right_nb", [], user_id)],
                user_id,
            )
        case "q":
            await finish("ftt.quit", [], user_id)
        case "c":
            state["_steps"] = []
            return lang.text("ftt.step_clear_nb", [], user_id)


async def handle_steps_input(state: T_State, event: MessageEvent, steps: str) -> None:
    text = ""
    for s in steps.split(" "):
        text += await handle_steps(state, s, event.user_id) or ""
    if len(state["_steps"]) == len(state["answer"]):
        await ftt.reject(lang.text("ftt.step_done", [], event.user_id))
    await ftt.reject(
        lang.text(
            "ftt.map", [text, len(state["_steps"]), len(state["answer"])], event.user_id
        )
    )


def execute(steps: list[int], game_map: list[list[int]]) -> bool:
    game_map, pos = search.get_start_pos(game_map)
    for step in steps:
        game_map = search.parse_sand(game_map, pos)
        game_map, pos = search.move(game_map, pos, step)
    return search.get_item_by_pos(pos, game_map) == const.TERMINAL


def parse_steps_input(steps: str) -> str:
    return " ".join([char for char in list(steps) if char])


@ftt.got("steps")
async def _(state: T_State, event: MessageEvent, steps: str = ArgPlainText("steps")):
    try:
        if len(state["_steps"]) != len(state["answer"]):
            await handle_steps_input(state, event, parse_steps_input(steps))
        elif steps == "clear":
            state["_steps"] = []
            await ftt.reject(
                lang.text(
                    "ftt.map",
                    [
                        lang.text("ftt.step_clear_nb", [], event.user_id),
                        len(state["_steps"]),
                        len(state["answer"]),
                    ],
                    event.user_id,
                )
            )
        elif steps == "quit":
            await finish("ftt.quit", [], event.user_id)
        elif steps == "ok":
            if execute(state["_steps"], copy.deepcopy(state["map"])):
                await finish("ftt.success", [], event.user_id)
            else:
                state["_steps"] = []
                await ftt.reject(lang.text("ftt.fail", [], event.user_id))
        await ftt.reject(lang.text("ftt.step_done", [], event.user_id))
    except Exception:
        await error.report()


# [HELPSTART] Version: 2
# Command: ftt
# Msg: 寻径指津
# Info: 开始「寻径指津」小游戏（玩法说明见 https://xdbot2.itcdt.top/games/ftt）
# Usage: ftt [{easy|normal}]
# [HELPEND]
