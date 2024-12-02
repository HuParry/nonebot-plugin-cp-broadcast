import time
from datetime import timedelta

from httpx import AsyncClient
from nonebot.plugin import on_fullmatch, on_command
from nonebot.adapters.onebot.v11.message import Message
from nonebot.adapters.onebot.v11 import Bot, PrivateMessageEvent, GroupMessageEvent
from nonebot.params import CommandArg
from nonebot.rule import to_me
from typing import List
from .aiosqlite import *
from .config import ContestType
from .utils import *
import asyncio

###列表下标0为比赛名称、下标1为比赛时间、下标2为比赛链接
cf: List[ContestType] = []


async def get_today_data() -> List[ContestType]:
    """

    :return: 返回cf今天的比赛列表
    """
    global cf
    today = datetime.datetime.now().date()
    contest_list: List[ContestType] = []
    if len(cf) == 0:
        await get_data_cf()
    if len(cf) > 0:
        for each in cf:
            cur_time = datetime.datetime.strptime(str(each.get_time()), "%Y-%m-%d %H:%M").date()
            if cur_time == today:
                contest_list.append(each)

    return contest_list


async def get_next_data() -> List[ContestType]:
    """

    :return: 返回cf接下来的比赛列表
    """
    global cf
    tomorrow = datetime.datetime.now().date() + timedelta(days=1)
    contest_list: List[ContestType] = []
    if len(cf) == 0:
        await get_data_cf()
    if len(cf) > 0:
        for each in cf:
            cur_time = datetime.datetime.strptime(str(each.get_time()), "%Y-%m-%d %H:%M").date()
            if cur_time >= tomorrow:
                contest_list.append(each)

    return contest_list


async def get_data_cf() -> bool:
    global cf
    url = 'https://codeforces.com/api/contest.list?gym=false'
    num = 0  # 尝试获取的次数，最多尝试三次
    while num < 3:
        try:
            if len(cf) > 0:
                cf.clear()
            async with AsyncClient() as client:
                r = await client.get(url, timeout=10)
            for each in r.json()['result'][0::]:
                if each['phase'] != "BEFORE":
                    break
                contest_name = each['name']
                contest_time = int(each['startTimeSeconds'])
                contest_url = f"https://codeforces.com/contest/{str(each['id'])}"
                contest_length = int(each['durationSeconds'])

                cf.append(ContestType(contest_name, contest_time, contest_url, contest_length))
            cf.reverse()
            return True
        except:
            num += 1
            await asyncio.sleep(2)  # 两秒后再次获取信息
    return False


async def ans_cf() -> str:
    global cf
    if len(cf) == 0:
        await get_data_cf()
    if len(cf) == 0:
        return f'突然出错了，稍后再试哦~'
    msg = []
    tot = 0
    for each in cf:
        msg.append(to_context(each))
        tot += 1
        if tot >= 3:
            break
    return '\n'.join( [f"找到最近的 {tot} 场cf比赛为："] + msg )


cf_matcher = on_fullmatch('cf', priority=80, block=True)
bind = on_command('cf监视', rule=to_me(), priority=80, block=True)
bind_remove = on_command('cf监视移除', rule=to_me(), priority=80, block=True)
bind_list = on_fullmatch('cf监视列表', rule=to_me(), priority=78, block=True)
query = on_command('cf查询', rule=to_me(), priority=79, block=True)
rank = on_command('cf排名', rule=to_me(), priority=80, block=True)
remarks = on_command('cf监视备注', rule=to_me(), priority=80, block=True)


@cf_matcher.handle()
async def reply_handle():
    msg = await ans_cf()
    await cf_matcher.finish(msg)


@bind.handle()
async def bind_handle(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    cfid = args.extract_plain_text()
    if cfid:
        status = await addUser(cfid)
        if status:
            await bind.finish(f'监视{cfid}成功！')
        else:
            await bind.finish(f'监视{cfid}失败！请检查该用户是否存在')
    else:
        await bind.finish('绑定失败，请按照格式发起指令！')


@bind_remove.handle()
async def bind_remove_handle(args: Message = CommandArg()):
    cfid = args.extract_plain_text()
    if cfid:
        status = await removeUser(cfid)
        if status:
            await bind_remove.finish(f'{cfid}移除成功')
        else:
            await bind_remove.finish(f'{cfid}移除失败')


@bind_list.handle()
async def bind_list_handle():
    msg = await returnBindList()
    await bind_list.finish(msg)


@query.handle()
async def query_handle(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    cfid = args.extract_plain_text()
    if cfid:
        msg = await queryUser(cfid)
        await query.finish(msg)
    else:
        await bind.finish('绑定失败，请按照格式发起指令！')


@rank.handle()
async def rank_handle(bot: Bot):
    data = await returnRanklist()
    msg = '当前rating排名如下：\n'
    for person in data:
        msg += f'{person[0]} {person[1]}\n'

    await rank.finish(msg)


@remarks.handle()
async def remarks_handle(bot: Bot, args: Message = CommandArg()):
    cf_list = args.extract_plain_text().split(' ')
    if len(cf_list) != 2:
        remarks.finish('格式不正确，请重新触发指令')

    cf_id, cf_remarks = cf_list
    status = await modifyRemarks(cf_id, cf_remarks)
    if status:
        await remarks.finish('设置成功！')
    else:
        await remarks.finish('设置失败！')
