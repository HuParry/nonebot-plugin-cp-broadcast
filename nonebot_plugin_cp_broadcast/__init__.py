from .config import Config
from nonebot import get_driver
import urllib.request
import datetime
from datetime import timedelta
import time

from httpx import AsyncClient

from bs4 import BeautifulSoup
from nonebot.plugin import on_fullmatch
from nonebot import require, get_bot
from nonebot.rule import to_me
#from nonebot.adapters.onebot.v11 import Bot, Event
from fake_useragent import FakeUserAgent
from nonebot.adapters.onebot.v11.message import Message
from nonebot.log import logger
import asyncio
import re

cp_broadcast_list = Config.parse_obj(get_driver().config.dict()).cp_broadcast_list
cp_broadcast_botname = Config.parse_obj(get_driver().config.dict()).cp_broadcast_botname
cp_broadcast_time = Config.parse_obj(get_driver().config.dict()).cp_broadcast_time
cp_broadcast_updatetime = Config.parse_obj(get_driver().config.dict()).cp_broadcast_updatetime

from nonebot.plugin import PluginMetadata

__plugin_meta__ = PluginMetadata(
    name="算法竞赛比赛查询",
    description="可以查询牛客、atcoder、codeforces平台的今天和近几天的比赛信息",
    usage="cf->查询cf比赛\n"\
        "nc/牛客->查询牛客比赛\n"\
        "atc->查询atcoder比赛\n"\
        "today->查询今天的比赛\n"\
        "next->查询明天之后的部分比赛\n"
        "update->更新比赛数据\n"\
        "about->{botname}的一些信息\n",
    type="application",
    homepage="https://github.com/HuParry/nonebot-plugin-cp-broadcast",
    config=Config,
    supported_adapters = {"nonebot.adapters.onebot.v11"},
    extra={
        "unique_name": "cp-broadcast",
        "example": "today",
        "author": "HuParry <huparry@outlook.com>",
        "version": "0.1.5",
    }
)


try:
    scheduler = require("nonebot_plugin_apscheduler").scheduler
except BaseException:
    scheduler = None

headers = {
    'user-agent': FakeUserAgent().random
}
###列表下标0为比赛名称、下标1为比赛时间、下标2为比赛链接
cf = [] 
atc = []
nc = []
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

async def get_data_atc() -> bool:  #以元组形式插入列表中，从左到右分别为比赛名称、比赛时间、比赛链接
    global atc
    url = f'https://atcoder.jp/contests/?lang=en'
    num = 0 #爬取次数，最多爬三次
    while num < 3 :
        try:
            if len(atc) > 0:
                atc.clear()
            html = urllib.request.urlopen(url).read()
            soup = BeautifulSoup(html,'lxml').find_all(name = 'div', attrs = {'id' : 'contest-table-upcoming'})[0].find_all('tbody')[0].find_all('td')
            ans1 = str(soup[1].contents[5].contents[0])
            url1 = 'https://atcoder.jp' + re.findall(r'<a href="(.+?)">',str(soup[1]))[0]
            ss = str(soup[0].contents[0].contents[0].contents[0]).replace('+0900', '')
            ans2 = str(datetime.datetime.strptime(ss, '%Y-%m-%d %H:%M:%S') - datetime.timedelta(hours = 1))
            ans2 = ans2[0:-3]
            ans3 = str(soup[5].contents[5].contents[0])
            url2 = 'https://atcoder.jp' + re.findall(r'<a href="(.+?)">',str(soup[5]))[0]
            ss1 = str(soup[4].contents[0].contents[0].contents[0]).replace('+0900', '')
            ans4 = str(datetime.datetime.strptime(ss1, '%Y-%m-%d %H:%M:%S') - datetime.timedelta(hours = 1))
            ans4 = ans4[0:-3]
            atc.append([ans1, ans2, url1])
            atc.append([ans3, ans4, url2])
            return True
        except:
            num += 1
            await asyncio.sleep(2)
    return False

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
    

async def ans_atc() -> str:
    global atc
    try:
        if len(atc) == 0:
            await get_data_atc()
        if len(atc) == 0:
            return f'突然出错了，稍后再试哦~'
        return f"找到最近的 2 场atc比赛为：\n" \
            + '比赛名称：' + atc[0][0] + '\n' + '比赛时间：' + atc[0][1] + '\n' +'比赛链接：' + atc[0][2] + '\n'\
            + '比赛名称：' + atc[1][0] + '\n' + '比赛时间：' + atc[1][1] + '\n' +'比赛链接：' + atc[1][2]
    except:
        return f'突然出错了，稍后再试哦~'

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


async def ans_today():  #today
    global cf
    global atc
    global nc
    msg = ''
    n = 0
    today = datetime.datetime.now().date()
    if len(cf) == 0:
        await get_data_cf()
    if len(cf) > 0:
        for each in cf:
            cur_time = datetime.datetime.strptime(str(each[1]), "%Y-%m-%d %H:%M").date()
            if cur_time == today:
                if n == 0:
                    msg += '◉cf比赛：\n'
                msg += '比赛名称：' + each[0] + '\n'\
                    + '比赛时间：' + each[1] +'\n'\
                    f'比赛链接：' + each[2] + '\n'
                n = 1
            else:
                break
    n = 0 
    msg2 = ''
    if len(nc) == 0:
        await get_data_nc()
    if len(nc) > 0:
        #second = '{:.3f}'.format(time.time())
        #second2 = int(float(second)*1000)
        for data in nc:
            cur_time = datetime.datetime.strptime(str(data[1]), "%Y-%m-%d %H:%M").date()
            if  cur_time == today:
                if n == 0:
                    msg2 += '◉牛客比赛：\n'
                    n = 1
                msg2 += "比赛名称：" + data[0] + '\n'
                msg2 += "比赛时间：" + data[1] + '\n'
                msg2 += "比赛链接：" + data[2] +'\n'

    n=0
    msg3 = ''
    
    if len(atc) == 0:
        await get_data_atc()
    
    if len(atc) > 0:
        for each in atc:
            cur_time = datetime.datetime.strptime(str(each[1]), "%Y-%m-%d %H:%M").date()
            if cur_time == today:
                if n == 0:
                    msg3 += '◉atc比赛：\n'
                msg3 += '比赛名称：' + each[0] + '\n'\
                    + '比赛时间：' + each[1] + '\n'\
                    + '比赛链接：' + each[2] + '\n'
    
    if len(cf) == 0 and len(nc) == 0 and len(atc) == 0:
        return f'查询出错了，稍后再尝试哦~'
    if msg == '' and msg2 == '' and msg3 == '':
        return '今天没有比赛，但也要好好做题哦~'
    return '找到今天的比赛如下：\n' + msg + msg2 +msg3

async def ans_next():
    global cf
    global atc
    global nc
    tomorrow = datetime.datetime.now().date() + timedelta(days=1)
    msg = ''
    flag = 0
    n = 0
    if len(cf) == 0:
        await get_data_cf()
    if len(cf) > 0:
        for each in cf :
            cur_time = datetime.datetime.strptime(str(each[1]), "%Y-%m-%d %H:%M").date()
            if  cur_time >= tomorrow:
                if flag == 0:
                    msg += '◉cf比赛：\n'
                    flag = 1
                msg += '比赛名称：' + each[0] + '\n'\
                    + '比赛时间：' + each[1] +'\n' \
                    + '比赛链接：' + each[2] + '\n'
                n += 1
            if n >= 2 :
                break
    n = 0
    flag = 0
    msg2 = ''
    
    if len(nc) == 0:
        await get_data_nc()
    if len(nc) > 0:
        for data in nc:
            cur_time = datetime.datetime.strptime(str(data[1]), "%Y-%m-%d %H:%M").date()
            if cur_time >= tomorrow:
                if flag == 0:
                    msg2 += '◉牛客比赛：\n'
                    flag = 1
                msg2 += "比赛名称：" + data[0] + '\n'
                msg2 += "比赛时间：" + data[1] + '\n'
                msg2 += "比赛链接：" + data[2] +'\n'
                n += 1
            if n >= 2:
                break

    msg3 = ''
    flag = 0

    if len(atc) == 0:
        await get_data_atc()
    if len(atc) > 0:
        for each in atc:
            cur_time = datetime.datetime.strptime(str(each[1]), "%Y-%m-%d %H:%M").date()
            if cur_time >= tomorrow:
                if flag == 0:
                    msg3 += '◉atc比赛：\n'
                    flag = 1
                msg3 += '比赛名称：' + (each[0]) + '\n'\
                    + '比赛时间：' + (each[1]) + '\n'\
                    + '比赛链接：' + (each[2]) + '\n'

    if len(cf) == 0 and len(nc) == 0 and len(atc) == 0:
        return f'查询出错了，稍后再尝试哦~'
    if msg == '' and msg2 == '' and msg3 == '':
        return '接下来几天没有比赛，但也要好好做题哦~'
    return '找到接下来的比赛如下：\n' + msg + msg2 +msg3

cf_matcher = on_fullmatch('cf',priority = 80,block=True)
@cf_matcher.handle()
async def reply_handle():
    msg = await ans_cf()
    await cf_matcher.finish(msg)

atc_matcher = on_fullmatch('atc',priority = 80,block=True)
@atc_matcher.handle()
async def reply_handle():
    msg = await ans_atc()
    await atc_matcher.finish(msg)

nc_matcher = on_fullmatch(('牛客', 'nc'),priority=70,block=True)
@nc_matcher.handle()
async def _():
    msg = await ans_nc()
    await nc_matcher.finish(msg)

today_matcher = on_fullmatch('today',priority=70,block=True)
@today_matcher.handle()
async def _():
    msg = await ans_today()
    await today_matcher.finish(msg)

next_matcher = on_fullmatch('next', priority=70, block=True)
@next_matcher.handle()
async def _():
    msg = await ans_next()
    await next_matcher.finish(msg)

help = on_fullmatch(('help','帮助'),block=True,priority=70,rule=to_me())
@help.handle()
async def help_():
    msg = __plugin_meta__.usage.format(botname=cp_broadcast_botname)

    await help.finish(msg)

#清晨自动播报比赛
async def auto_broadcast():
    await asyncio.sleep(1)
    for id in cp_broadcast_list:
        await asyncio.sleep(2)
        await get_bot().send_group_msg(group_id=id, message='早上好呀！'+ await ans_today())

if scheduler:
    scheduler.add_job(auto_broadcast, 
                      "cron", hour=cp_broadcast_time['hour'],minute=cp_broadcast_time['minute'],id="_-"
                      )

#凌晨12点自动更新比赛信息
async def update():
    global cf
    global atc
    global nc
    cf.clear()
    atc.clear()
    nc.clear()

    if await get_data_cf():
        logger.info('cf比赛信息更新成功')
    if await get_data_nc():
        logger.info('牛客比赛信息更新成功')
    if await get_data_atc():
        logger.info('atc比赛信息更新成功')

if scheduler:
    scheduler.add_job(
        update, "cron", hour=cp_broadcast_updatetime['hour'],minute=cp_broadcast_updatetime['minute'],id="update"
        )

#更新数据
update_matcher = on_fullmatch('update', priority=70, block=True)
@update_matcher.handle()
async def reply():
    await update()
    await update_matcher.finish('数据已更新完成')