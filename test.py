import re
import datetime
import time

from bs4 import BeautifulSoup
from httpx import AsyncClient

import requests
atc = []
url = f'https://atcoder.jp/contests/?lang=en'
resp = requests.get(url=url, timeout=10.0)

soup = \
    BeautifulSoup(resp.text, 'lxml').find_all(name='div', attrs={'id': 'contest-table-upcoming'})[
        0].find_all(
        'tbody')[0].find_all('td')



ans1 = str(soup[1].contents[5].contents[0])

url1 = re.findall(r'<td class="text-center">(.+?)</td>', str(soup[2]))[0]

ss = str(soup[0].contents[0].contents[0].contents[0]).replace('+0900', '')
print(ss)
ans2 = str(datetime.datetime.strptime(ss, '%Y-%m-%d %H:%M:%S') - datetime.timedelta(hours=1))
contest1_time = int(time.mktime(time.strptime(ans2, "%Y-%m-%d %H:%M:%S")))
print(contest1_time)
ans2 = ans2[0:-3]
print(ans2)
ans3 = str(soup[5].contents[5].contents[0])
url2 = 'https://atcoder.jp' + re.findall(r'<a href="(.+?)">', str(soup[5]))[0]
ss1 = str(soup[4].contents[0].contents[0].contents[0]).replace('+0900', '')
ans4 = str(datetime.datetime.strptime(ss1, '%Y-%m-%d %H:%M:%S') - datetime.timedelta(hours=1))
ans4 = ans4[0:-3]
atc.append([ans1, ans2, url1])
atc.append([ans3, ans4, url2])
