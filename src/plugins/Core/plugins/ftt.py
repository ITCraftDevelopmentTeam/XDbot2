import asyncio
import random
from typing import Literal
from ._utils import *
from src.plugins.Core.lib.FindingTheTrail import search, const, image, map, argv
from nonebot.params import ArgPlainText
from nonebot.typing import T_State
import copy
import asyncio
import multiprocessing

ftt = on_command("ftt", aliases={"FindingTheTrail"})


def get_difficulty():
    if random.random() <= 0.5:
        return "easy"
    else:
        return random.choice(list(argv.ARGUMENTS.keys()))


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


DIRECTION_TEXT = {
    const.UP: "up",
    const.DOWN: "down",
    const.LEFT: "left",
    const.RIGHT: "right",
}


async def sendExampleAnswer(
    answer: list[int], userId: int, gameMap: list[list[int]]
) -> None:
    await send_text(
        "ftt.exampleAnswer",
        [
            lang.text("ftt.exampleAnswerSep_nb", [], userId).join(
                [
                    lang.text(f"ftt.step_{DIRECTION_TEXT[step]}_nb", [], userId)
                    for step in answer
                ]
            ),
            getAnswerSegment(gameMap, answer),
        ],
        userId,
    )


from .pawcoin import usePawCoin
from .etm.exception import NoPawCoinException


@ftt.handle()
async def _(
    state: T_State, bot: Bot, event: MessageEvent, message: Message = CommandArg()
) -> None:
    global cacheCreateProcess
    try:
        await usePawCoin(event.get_user_id(), 1)
        difficulty = message.extract_plain_text().strip() or get_difficulty()
        if difficulty not in argv.ARGUMENTS.keys():
            await finish(get_currency_key("unknown_argv"), [difficulty], event.user_id)
        message_id = await send_message(bot, event, "ftt.generating_map")
        state["map"], state["answer"] = await getGameMap(difficulty)
        await bot.delete_msg(message_id=message_id)
        await send_text(
            "ftt.map",
            [
                MessageSegment.image(image.generateImage(state["map"])),
                0,
                len(state["answer"]),
            ],
            event.user_id,
            True,
        )
        state["_steps"] = []
        state["prize_vi"] = {"normal": 1.5, "easy": 1, "hard": 2}.get(
            difficulty, 0
        ) * random.randint(len(state["answer"]) * 3, len(state["answer"]) * 4)
        if not cacheCreateProcess.is_alive():
            cacheCreateProcess = multiprocessing.Process(target=createMapCache)
            cacheCreateProcess.start()
    except NoPawCoinException:
        await finish("_utils.noPawCoin", [], event.user_id)
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
            await sendExampleAnswer(state["answer"], user_id, state["map"])
            await finish("ftt.quit", [], user_id)
        case "c":
            state["_steps"] = []
            return lang.text("ftt.step_clear_nb", [], user_id)


async def handle_steps_input(state: T_State, event: MessageEvent, steps: str) -> None:
    text = ""
    for s in steps.split(" "):
        text += await handle_steps(state, s, event.user_id) or ""
        # try:
        #     execute(state["_steps"], copy.deepcopy(state["map"]))
        # except InvalidMoveError as e:
        #     state["_steps"] = state["_steps"][:-1]
        #     await send_text("ftt.invalid_move", [e.step_index], event.user_id)
        #     await ftt.reject(
        #         lang.text(
        #             "ftt.map",
        #             [text, len(state["_steps"]), len(state["answer"])],
        #             event.user_id,
        #         )
        #     )
    if len(state["_steps"]) == len(state["answer"]):
        await ftt.reject(lang.text("ftt.step_done", [], event.user_id))
    await ftt.reject(
        lang.text(
            "ftt.map", [text, len(state["_steps"]), len(state["answer"])], event.user_id
        )
    )


import io

from PIL import Image


def generateMapFrame(gameMap: list[list[int]], pos: tuple[int, int]) -> Image.Image:
    gameMap = copy.deepcopy(gameMap)
    gameMap[pos[0]][pos[1]] = const.START
    return image.generate(gameMap)


def generateAnswerGif(gameMap: list[list[int]], steps: list[int]) -> bytes:
    gameMap, pos = search.get_start_pos(copy.deepcopy(gameMap))
    imgs = [generateMapFrame(gameMap, pos)]
    for step in steps:
        _pos = pos
        gameMap, pos = search.move(gameMap, pos, step)
        if pos != _pos:
            gameMap = search.parse_sand(gameMap, _pos)
        imgs.append(generateMapFrame(gameMap, pos))
    buffer = io.BytesIO()
    imgs[0].save(
        buffer, "GIF", save_all=True, append_images=imgs[1:], duration=500, loop=0
    )
    return buffer.getvalue()


def getAnswerSegment(gameMap: list[list[int]], steps: list[int]) -> MessageSegment:
    return MessageSegment.image(generateAnswerGif(gameMap, steps))


class InvalidMoveError(Exception):
    def __init__(self, step_index: int, *args: object) -> None:
        super().__init__(*args)
        self.step_index = step_index


def execute(steps: list[int], game_map: list[list[int]]) -> bool:
    game_map, pos = search.get_start_pos(game_map)
    length = 0
    for step in steps:
        _pos = pos
        game_map, pos = search.move(game_map, pos, step)
        if pos == _pos:
            raise InvalidMoveError(length)
        length += 1
        game_map = search.parse_sand(game_map, _pos)
    return search.get_item_by_pos(pos, game_map) == const.TERMINAL


def parse_steps_input(steps: str) -> str:
    return " ".join([char for char in list(steps) if char])


from .etm.economy import add_vi


async def handle_wrong_answer(
    state: T_State,
    event: MessageEvent,
    fail_type: Literal["fail", "invalid"] = "fail",
    invalid_step_length: int = -1,
) -> None:
    state["prize_vi"] -= 5
    _steps = state["_steps"]
    state["_steps"] = []
    if state["prize_vi"] >= 0:
        await ftt.reject(
            Message(
                lang.text(
                    f"ftt.{fail_type}",
                    [getAnswerSegment(state["map"], _steps)],
                    event.user_id,
                    params={"step": str(invalid_step_length)},
                )
            )
        )
    else:
        await sendExampleAnswer(state["answer"], event.user_id, state["map"])
        await finish(
            f"ftt.{fail_type}_no_vi",
            [getAnswerSegment(state["map"], _steps), invalid_step_length],
            event.user_id,
            parse_cq_code=True,
            step=str(invalid_step_length),
        )


async def check_answer(state: T_State, event: MessageEvent) -> None:
    try:
        result = execute(state["_steps"], copy.deepcopy(state["map"]))
    except InvalidMoveError as e:
        await handle_wrong_answer(state, event, "invalid", e.step_index + 1)
    if result:
        add_vi(event.get_user_id(), state["prize_vi"])
        await finish(
            "ftt.success",
            [state["prize_vi"], getAnswerSegment(state["map"], state["_steps"])],
            event.user_id,
            parse_cq_code=True,
        )
    else:
        await handle_wrong_answer(state, event)


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
            await sendExampleAnswer(state["answer"], event.user_id, state["map"])
            await finish("ftt.quit", [], event.user_id)
        elif steps == "ok":
            await check_answer(state, event)
        await ftt.reject(lang.text("ftt.step_done", [], event.user_id))
    except Exception:
        await error.report()


# [HELPSTART] Version: 2
# Command: ftt
# Msg: 寻径指津
# Info: 开始「寻径指津」小游戏（玩法说明见 https://xdbot2.itcdt.top/games/ftt）
# Usage: ftt [{easy|normal|hard}]
# [HELPEND]
