import time
from httpx import AsyncClient
from nonebot.plugin import on_fullmatch
from nonebot.adapters.onebot.v11.message import Message
import asyncio

###列表下标0为比赛名称、下标1为比赛时间、下标2为比赛链接
cf = [] 

async def get_data_cf() -> bool:
    global cf
    url = 'https://codeforces.com/api/contest.list?gym=false'
    num = 0 #尝试获取的次数，最多尝试三次
    while num < 3 :
        try:
            if(len(cf) > 0):
                cf.clear()
            async with AsyncClient() as client:
                r = await client.get(url, timeout=10)
            for each in r.json()['result'][0::]:
                if each['phase'] != "BEFORE":
                    break
                contest_name = each['name']
                contest_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(each['startTimeSeconds']))
                id = each['id']
                contest_url = f'https://codeforces.com/contest/{id}'
                cf.append([contest_name, contest_time, contest_url])  #从左到右分别为比赛名称、比赛时间、比赛链接
            cf.reverse()
            return True
        except:
            num += 1
            await asyncio.sleep(2)  #两秒后再次获取信息
    return False

async def ans_cf() -> str:
    global cf
    if len(cf) == 0:
        await get_data_cf()
    if len(cf) == 0:
        return f'突然出错了，稍后再试哦~'
    msg = ''
    tot = 0
    for each in cf:
        msg += '比赛名称：' + each[0] + '\n'\
            + '比赛时间：' + each[1] + '\n'\
            + '比赛链接' + each[2]
        tot += 1
        if (tot != 3):
            msg += '\n'
        else:
            break
    return f"找到最近的 {tot} 场cf比赛为：\n" + msg

cf_matcher = on_fullmatch('cf',priority = 80,block=True)
@cf_matcher.handle()
async def reply_handle():
    msg = await ans_cf()
    await cf_matcher.finish(msg)