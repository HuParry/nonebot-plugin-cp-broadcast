# import urllib.request
import time

from httpx import AsyncClient
import datetime
from bs4 import BeautifulSoup
from nonebot.plugin import on_fullmatch
from nonebot.adapters.onebot.v11.message import Message
from nonebot.log import logger
from typing import List
from .config import ContestType
import asyncio
import re

###列表下标0为比赛名称、下标1为比赛时间、下标2为比赛链接
atc: List[ContestType] = []


async def get_today_data() -> List[ContestType]:
    global atc
    if len(atc) == 0:
        await get_data_atc()

    today = datetime.datetime.now().date()
    contest_list: List[ContestType] = []
    if len(atc) > 0:
        for each in atc:
            cur_time = datetime.datetime.strptime(str(each.get_time()), "%Y-%m-%d %H:%M").date()
            if cur_time == today:
                contest_list.append(each)

    return contest_list


async def get_next_data() -> List[ContestType]:
    global atc
    if len(atc) == 0:
        await get_data_atc()

    tomorrow = datetime.datetime.now().date() + datetime.timedelta(days=1)
    contest_list: List[ContestType] = []
    if len(atc) > 0:
        for each in atc:
            cur_time = datetime.datetime.strptime(str(each.get_time()), "%Y-%m-%d %H:%M").date()
            if cur_time >= tomorrow:
                contest_list.append(each)

    return contest_list


async def get_data_atc() -> bool:  # 以元组形式插入列表中，从左到右分别为比赛名称、比赛时间、比赛链接
    global atc
    url = f'https://atcoder.jp/contests/?lang=en'
    num = 0  # 爬取次数，最多爬三次
    while num < 3:
        try:
            if len(atc) > 0:
                atc.clear()

            async with AsyncClient() as client:
                resp = await client.get(url=url, timeout=10.0)

            soup = \
                BeautifulSoup(resp.text, 'lxml').find_all(name='div', attrs={'id': 'contest-table-upcoming'})[
                    0].find_all(
                    'tbody')[0].find_all('td')
            contest1_name = str(soup[1].contents[5].contents[0])
            ss = str(soup[0].contents[0].contents[0].contents[0]).replace('+0900', '')
            contest1_time1 = str(datetime.datetime.strptime(ss, '%Y-%m-%d %H:%M:%S') - datetime.timedelta(hours=1))
            contest1_time = int(time.mktime(time.strptime(contest1_time1, "%Y-%m-%d %H:%M:%S")))
            contest1_length = re.findall(r'<td class="text-center">(.+?)</td>', str(soup[2]))[0]
            length_list1 = contest1_length.split(':')

            contest2_name = str(soup[5].contents[5].contents[0])
            ss1 = str(soup[4].contents[0].contents[0].contents[0]).replace('+0900', '')
            contest2_time2 = str(datetime.datetime.strptime(ss1, '%Y-%m-%d %H:%M:%S') - datetime.timedelta(hours=1))
            contest2_time = int(time.mktime(time.strptime(contest2_time2, "%Y-%m-%d %H:%M:%S")))
            contest2_length: str = re.findall(r'<td class="text-center">(.+?)</td>', str(soup[2]))[0]
            length_list2 = contest2_length.split(':')

            atc.append(ContestType(contest1_name, contest1_time, int(length_list1[0]) * 3600 + int(length_list1[1]) * 60))
            atc.append(ContestType(contest2_name, contest2_time, int(length_list2[0]) * 3600 + int(length_list2[1]) *60))

            return True
        except Exception as e:
            logger.warning(str(e))
            num += 1
            await asyncio.sleep(2)
    return False


async def ans_atc() -> str:
    global atc
    try:
        if len(atc) == 0:
            await get_data_atc()
        if len(atc) == 0:
            return f'突然出错了，稍后再试哦~'
        msg = f"找到最近的 2 场atc比赛为：\n"
        for each in atc:
            msg += f"比赛名称：{each.get_name()}\n比赛时间：{each.get_time()}\n比赛时长：{each.get_length()}分钟\n"
        return msg
    except:
        return f'突然出错了，稍后再试哦~'


atc_matcher = on_fullmatch('atc', priority=80, block=True)


@atc_matcher.handle()
async def reply_handle():
    msg = await ans_atc()
    await atc_matcher.finish(msg)
