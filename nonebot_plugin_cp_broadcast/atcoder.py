import urllib.request
import datetime
from bs4 import BeautifulSoup
from nonebot.plugin import on_fullmatch
from nonebot.adapters.onebot.v11.message import Message
import asyncio
import re


###列表下标0为比赛名称、下标1为比赛时间、下标2为比赛链接
atc = []

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
    
atc_matcher = on_fullmatch('atc',priority = 80,block=True)
@atc_matcher.handle()
async def reply_handle():
    msg = await ans_atc()
    await atc_matcher.finish(msg)