import datetime
import time

from json import loads
from html import unescape
from bs4 import BeautifulSoup, NavigableString, ResultSet, Tag
from httpx import AsyncClient, Response
from httpx._types import URLTypes, ProxiesTypes

from nonebot.plugin import on_fullmatch
from fake_useragent import FakeUserAgent
from nonebot.adapters.onebot.v11.message import Message
import asyncio
from typing import Any, Dict, Literal, Optional, TypedDict, List, Union

from .config import ContestType
from .utils import *

headers = {
    'user-agent': FakeUserAgent().random
}

###列表下标0为比赛名称、下标1为比赛时间、下标2为比赛链接
nc: List[ContestType] = []


async def req_get(url: URLTypes, proxies: Optional[ProxiesTypes] = None) -> str:
    """
    生成一个异步的GET请求

    Args:
        url (URLTypes): 对应的URL

    Returns:
        str: URL对应的HTML
    """
    async with AsyncClient(proxies=proxies) as client:
        r: Response = await client.get(url)
    return r.content.decode("utf-8")


async def get_data_nc(url: str = "https://ac.nowcoder.com/acm/contest/vip-index") -> List[ContestType]:
    """
    处理牛客的竞赛列表

    Args:
        content (str): HTML

    Returns:
        list: 竞赛列表
    """

    global nc
    content = await req_get(url)
    soup = BeautifulSoup(content, 'html.parser')
    find_item: Union[Tag, NavigableString, None] = soup.find('div', class_='platform-mod js-current')
    if not isinstance(find_item, Tag):
        return nc
    datatable: ResultSet = find_item.find_all('div', class_='platform-item js-item')

    for contest in datatable:
        cdata: Dict[str, Any] = loads(unescape(contest.get("data-json")))
        id = unescape(contest.get("data-id"))
        cdata["contestId"] = id
        contest_url = f"https://ac.nowcoder.com/acm/contest/{cdata['contestId']}"
        if cdata:
            nc.append(ContestType(cdata['contestName'], int(cdata["contestStartTime"] / 1000),
                                  contest_url, cdata["contestDuration"] / 1000))

    return nc


async def get_today_data() -> List[ContestType]:
    """

    :return: 返回今天的牛客比赛
    """
    global nc
    contest_list: List[ContestType] = []
    if len(nc) == 0:
        await get_data_nc()

    if len(nc) > 0:
        # second = '{:.3f}'.format(time.time())
        # second2 = int(float(second)*1000)

        today = datetime.datetime.now().date()
        for each in nc:
            cur_time = datetime.datetime.strptime(str(each.get_time()), "%Y-%m-%d %H:%M").date()
            if cur_time == today:
                contest_list.append(each)

    return contest_list


async def get_next_data() -> List[ContestType]:
    """

    :return: 返回接下来的比赛
    """
    global nc
    msg2 = ''
    n = 0
    contest_list: List[ContestType] = []
    if len(nc) == 0:
        await get_data_nc()

    if len(nc) > 0:
        # second = '{:.3f}'.format(time.time())
        # second2 = int(float(second)*1000)

        tomorrow = datetime.datetime.now().date() + datetime.timedelta(days=1)
        for each in nc:
            cur_time = datetime.datetime.strptime(str(each.get_time()), "%Y-%m-%d %H:%M").date()
            if cur_time >= tomorrow:
                contest_list.append(each)

    return contest_list


async def ans_nc() -> str:
    """

    :return: 返回牛客比赛的信息
    """
    global nc
    if len(nc) == 0:
        await get_data_nc()
    if len(nc) == 0:
        return f'突然出错了，稍后再试哦~'

    # second = '{:.3f}'.format(time.time())
    # second2 = int(float(second)*1000)
    msg = []
    n = 0
    for each in nc:
        n += 1
        msg.append(to_context(each))
        if n == 3:
            break
    return '\n'.join([f"找到最近的 {n} 场牛客比赛为：\n"] + msg)


nc_matcher = on_fullmatch(('牛客', 'nc'), priority=70, block=True)


@nc_matcher.handle()
async def _():
    msg = await ans_nc()
    await nc_matcher.finish(msg)
