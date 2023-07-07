from pydantic import BaseModel, Extra
from typing import List

class Config(BaseModel, extra=Extra.ignore):
    cp_broadcast_list: List[str] = []
    cp_broadcast_botname: str = "bot"
    cp_broadcast_time: dict[str, str] = {"hour" : "7", "minute" : "20"}
    cp_broadcast_updatetime: dict[str, str] = {"hour" : "0", "minute" : "0"}