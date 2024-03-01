import time

from pydantic import BaseModel, Extra
from typing import List, Dict, TypedDict
from pathlib import Path

from nonebot import get_driver, require

require("nonebot_plugin_localstore")

from nonebot_plugin_localstore import get_data_dir


class Config(BaseModel, extra=Extra.ignore):
    cp_broadcast_path: str = get_data_dir("nonebot_plugin_cp_broadcast")
    cp_broadcast_list: List[str] = []
    cp_broadcast_botname: str = "bot"
    cp_broadcast_time: Dict[str, str] = {"hour": "7", "minute": "20"}
    cp_broadcast_updatetime: Dict[str, str] = {"hour": "0", "minute": "0"}
    cp_broadcast_cf_list: List[str] = []
    cp_broadcast_cf_interval: int = 10


class ContestType:
    def __init__(self, contest_name: str, contest_time: int, contest_length: int):
        self.contest_name = contest_name
        self.contest_time = contest_time
        self.contest_length = contest_length

    def get_name(self) -> str:
        return self.contest_name

    def get_time(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(self.contest_time))

    def get_length(self) -> str:
        return f"{int(self.contest_length / 60)}"


cf_user_info_baseurl = 'https://codeforces.com/api/user.info?handles='
cf_user_status_baseurl = 'https://codeforces.com/api/user.status?handle={handle}&from=1&count=1'  # 查询交题记录，仅返回一个
cf_user_rating_baseurl = 'https://codeforces.com/api/user.rating?handle={handle}'

cp_broadcast_config = Config.parse_obj(get_driver().config.dict())
cp_broadcast_path = Path(cp_broadcast_config.cp_broadcast_path)
