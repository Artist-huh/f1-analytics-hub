"""Справочники в одном месте — data/reference.json: названия сессий, гражданства (флаг и страна по-русски),
страны трасс, шины. Раньше они жили в пяти модулях и расходились (у одного гражданства был флаг, но не было
названия). Полноту проверяет тест ReferenceTest.
"""
import json
import os

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "reference.json")

with open(PATH, encoding="utf-8") as _f:
    _data = json.load(_f)

SESSIONS = _data["sessions"]                    # ключ сессии (Jolpica или поток F1) -> «Квалификация»
REMIND_SESSIONS = _data["remind_sessions"]      # о каких сессиях напоминать
NATIONALITY_ISO = {k: v["iso"] for k, v in _data["nationalities"].items() if v.get("iso")}
NATIONS_RU = {k: v["ru"] for k, v in _data["nationalities"].items() if v.get("ru")}
COUNTRY_ISO = _data["countries"]                # страна трассы -> код флага
TYRES_RU = _data["tyres"]
