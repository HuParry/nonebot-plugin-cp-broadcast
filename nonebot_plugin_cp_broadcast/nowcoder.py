import datetime
import time
from httpx import AsyncClient
from nonebot.plugin import on_fullmatch
from fake_useragent import FakeUserAgent
from nonebot.adapters.onebot.v11.message import Message
import asyncio

headers = {
    'user-agent': FakeUserAgent().random
}

###列表下标0为比赛名称、下标1为比赛时间、下标2为比赛链接
nc = []

async def get_data_nc() -> bool:
    global nc
    url = 'https://ac.nowcoder.com/acm/calendar/contest'
    num = 0 #爬取次数,最大为3
    while num < 3:
        try:
            date = str(datetime.datetime.now().year) + ' - ' + str(datetime.datetime.now().month)
            second = '{:.3f}'.format(time.time())
            params = {
                'token': '',
                'month': date,
                '_': second
            }
            if(len(nc) > 0):
                nc.clear()
            
            async with AsyncClient() as client:
                r = await client.get(url, headers=headers, params=params, timeout=20)
            
            r = r.json()
            second2 = int(float(second)*1000)
            if r['msg'] == "OK" and r['code'] == 0 :
                for data in r["data"]:
                    if data["startTime"] >= second2:
                        contest_name = data["contestName"]
                        contest_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(data['startTime']/1000))
                        contest_url = data["link"]
                        nc.append([contest_name, contest_time, contest_url])
                return True
            else:
                return False
        except:
            num += 1
            await asyncio.sleep(2)
    return False


async def ans_nc() -> str:
    global nc
    if len(nc) == 0:
        await get_data_nc()
    if len(nc) == 0:
        return f'突然出错了，稍后再试哦~'
    #second = '{:.3f}'.format(time.time())
    #second2 = int(float(second)*1000)
    msg = ''
    n = 0
    for data in nc:
        n += 1
        msg += "比赛名称：" + data[0] + '\n'
        msg += "比赛时间：" + data[1] + '\n'
        msg += "比赛链接：" + data[2] + '\n'
        if n == 3:
            break
    return f"找到最近的 {n} 场牛客比赛为：\n" + msg

nc_matcher = on_fullmatch(('牛客', 'nc'),priority=70,block=True)
@nc_matcher.handle()
async def _():
    msg = await ans_nc()
    await nc_matcher.finish(msg)