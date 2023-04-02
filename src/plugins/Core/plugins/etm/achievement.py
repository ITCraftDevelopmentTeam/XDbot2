from .. import _messenger
from . import economy
from . import exp
import json
import time

ACHIEVEMENTS = json.load(open("src/plugins/Core/plugins/etm/achievement.json"))


def get_user_achievement(user_id):
    try:
        return json.load(open("data/etm/achievement.json", encoding="utf-8"))[user_id]
    except KeyError:
        return []


def change_user_achievement(user_id, data):
    user_data = json.load(open("data/etm/achievement.json", encoding="utf-8"))
    user_data[user_id] = data
    json.dump(user_data, open(
        "data/etm/achievement.json", "w", encoding="utf-8"))


def unlock(name, user_id):
    user_achievement = get_user_achievement(user_id)
    if name in ACHIEVEMENTS.keys() and name not in user_achievement:
        user_achievement.append(name)
        economy.add_vi(user_id, ACHIEVEMENTS[name]["award"]["vi"])
        exp.add_exp(user_id, ACHIEVEMENTS[name]["award"]["exp"])
        change_user_achievement(user_id, user_achievement)
        _messenger.send_message(
            (
                f"成就已解锁：{ACHIEVEMENTS[name]['name']}\n"
                f"时间：{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}"
            ),
            receive=user_id,
        )


def get_unlock_progress(name, user_id):
    user_data = json.load(
        open("data/etm/achievement_progress.json", encoding="utf-8"))
    try:
        return user_data[user_id][name]
    except KeyError:
        return None


def increase_unlock_progress(name, user_id, count=1):
    user_data = json.load(
        open("data/etm/achievement_progress.json", encoding="utf-8"))
    try:
        user_data[user_id][name] += count
    except KeyError:
        try:
            user_data[user_id][name] = count
        except KeyError:
            user_data[user_id] = {name: count}
    json.dump(
        user_data, open("data/etm/achievement_progress.json",
                        "w", encoding="utf-8")
    )
    if user_data[user_id][name] >= ACHIEVEMENTS[name]["need_progress"]:
        unlock(name, user_id)
