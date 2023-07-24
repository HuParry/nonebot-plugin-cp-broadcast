from pydantic import BaseModel, Extra
from typing import List, Dict
from pathlib import Path

from nonebot import get_driver

class Config(BaseModel, extra=Extra.ignore):
    cp_broadcast_list: List[str] = []
    cp_broadcast_botname: str = "bot"
    cp_broadcast_time: Dict[str, str] = {"hour" : "7", "minute" : "20"}
    cp_broadcast_updatetime: Dict[str, str] = {"hour" : "0", "minute" : "0"}
    cp_broadcast_cf_list: List[str] = []
    cp_broadcast_cf_interval: int = 10

cp_broadcast_path = Path() / "data" / "cp_broadcast"
cf_user_info_baseurl = 'https://codeforces.com/api/user.info?handles='


cp_broadcast_config = Config.parse_obj(get_driver().config.dict())