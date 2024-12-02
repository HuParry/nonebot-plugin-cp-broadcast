from typing import List

from nonebot.adapters.onebot.v11 import (
    Bot,
    MessageEvent,
    GroupMessageEvent,
)

from .config import ContestType


def to_context(contest: ContestType) -> str:
    return '\n'.join([
        f'比赛名称：{contest.get_name()}',
        f'比赛时间：{contest.get_time()}',
        f'比赛链接：{contest.get_url()}',
        f'比赛时长：{contest.get_length()}分钟',
        f'',
    ])


async def send_forward_msg(
        bot: Bot,
        event: MessageEvent,
        name: str,
        uin: str,
        msgs: List[str],
):
    def to_json(msg):
        return {"type": "node", "data": {"name": name, "uin": uin, "content": msg}}

    messages = [to_json(msg) for msg in msgs]
    if isinstance(event, GroupMessageEvent):
        await bot.call_api(
            "send_group_forward_msg", group_id=event.group_id, messages=messages
        )
    else:
        await bot.call_api(
            "send_private_forward_msg", user_id=event.user_id, messages=messages
        )
