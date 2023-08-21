import random
import json
from . import path
import os.path


def load_json(name: str) -> dict:
    return json.load(open(os.path.join(path.res_path, name), encoding="utf-8"))


def get_base_properties(_type: str = "primary") -> dict:
    return load_json(f"base_properties/{_type}")


class Monomer:
    def __init__(
        self, weapons: str, relics: dict[str, dict], ball: str, hp: int
    ) -> None:
        base_properties = get_base_properties()
        self._default_data = base_properties.copy()
        self.gain_list = []
        self.triggers = {}
        self.battle_skill_points = 3
        self.buff = []
        self.hp = hp

        self.enemy: Monomer

        self.get_weapons(weapons)
        self.get_ball(ball)
        self.get_kit_gain()

        self._default_data = self.parse_gain(self.gain_list)
        self.data = self._default_data.copy()
        del self.gain_list

    def get_kits(self) -> dict:
        kits = {}
        for relics_item in self.relics:
            kits[relics_item] = kits.get(relics_item, 0) + 1
        kits[self.weapons["kit"]] = kits.get(self.weapons["kit"], 0) + 1
        kits[self.ball["kit"]] = kits.get(self.ball["kit"], 0) + 1
        return kits

    def get_kit_gain(self) -> None:
        for kit, count in list(self.get_kits().items()):
            if count >= 2:
                self.gain_list += list(
                    load_json(f"kits/{kit}.json")["kit_effect"]["2"]
                    .get("gain", {})
                    .items()
                )
            if count >= 4:
                self.gain_list += list(
                    load_json(f"kits/{kit}.json")["kit_effect"]["4"]
                    .get("gain", {})
                    .items()
                )
            if count >= 6:
                self.gain_list += list(
                    load_json(f"kits/{kit}.json")["kit_effect"]["6"]
                    .get("gain", {})
                    .items()
                )
            if self.ball["kit"] == self.weapons["kit"]:
                self.gain_list += list(
                    load_json(f"kits/{kit}.json")["kit_effect"]["resonance"]
                    .get("gain", {})
                    .items()
                )

    def get_weapons(self, weapons: str) -> None:
        self.weapons = load_json(f"kits/{weapons}.json")["weapons"]
        self.weapons["kit"] = weapons
        if "gain" in self.weapons.keys():
            self.gain_list += self.weapons.items()

    def get_ball(self, ball: str) -> None:
        self.ball = load_json(f"kits/{ball}.json")["ball"]
        self.ball["kit"] = ball
        if "gain" in self.ball.keys():
            self.gain_list += self.ball.items()

    def get_relics_gain(self, relics: dict[str, dict]) -> None:
        self.relics = []
        for relics_item in list(relics.values()):
            self.relics.append(relics_item["kit"])
            self.gain_list += list(relics_item["gain"].items())

    def parse_gain(self, gain_list: list[tuple], base: dict | None = None) -> dict:
        default_data = base or self._default_data.copy()
        percentage_gain = {}
        for gain_name, value in gain_list:
            if isinstance(value, float):
                percentage_gain[gain_name] = percentage_gain.get(gain_name, 0.0) + value
            else:
                default_data[gain_name] = default_data.get(gain_name, 0) + value
        _default_data = default_data.copy()
        for key, value in list(percentage_gain.items()):
            default_data[key] = _default_data.get(key, 0) * (1 + value)
        return default_data

    def effect_add_hp(self, effect: dict) -> None:
        if isinstance(effect["value"], float):
            self.hp += self.data["health"] * (
                1 + effect["value"] + self.data["therapeutic_volume_bonus"]
            )
        else:
            self.hp += effect["value"] * (1 + self.data["therapeutic_volume_bonus"])

    def effect_add_trigger(self, effect: dict):
        if effect["condition"] not in self.triggers.keys():
            self.triggers[effect["condition"]] = []
        self.triggers[effect["condition"]].append(effect["effect"])

    def effect_add_battle_skill_points(self, effect: dict) -> None:
        if effect["target"]:
            if self.enemy.battle_skill_points < 5:
                self.enemy.battle_skill_points += 1
        elif self.battle_skill_points < 5:
            self.battle_skill_points += 1

    def effect_remove_battle_skill_points(self, effect: dict) -> None:
        if effect["target"]:
            if self.enemy.battle_skill_points > 0:
                self.enemy.battle_skill_points -= 1
        elif self.battle_skill_points > 0:
            self.battle_skill_points -= 1

    def parse_effect(self, effect_block: list[dict]) -> None:
        for effect in effect_block:
            match effect["function"]:
                case "add_hp":
                    self.effect_add_hp(effect)
                case "add_trigger":
                    self.effect_add_trigger(effect)
                case "verify_probabilities":
                    if random.random() > effect["probability"]:
                        break
                case "add_battle_skill_points":
                    self.effect_add_battle_skill_points(effect)
                case "remove_battle_skill_points":
                    self.effect_remove_battle_skill_points(effect)
                case "add_buff":
                    self.effect_add_buff(effect)

    def effect_add_buff(self, effect: dict) -> None:
        pass

    def prepare_before_action(self) -> None:
        pass

    def prepare_before_the_round(self) -> None:
        pass
