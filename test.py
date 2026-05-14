import re
import datetime
import time

from bs4 import BeautifulSoup
from httpx import AsyncClient
class ContestType:
    def __init__(self, contest_name: str, contest_time: int, contest_url: str, contest_length: int):
        self.contest_name = contest_name
        self.contest_time = contest_time
        self.contest_url = contest_url
        self.contest_length = contest_length

    def get_name(self) -> str:
        return self.contest_name

    def get_time(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(self.contest_time))

    def get_url(self) -> str:
        return self.contest_url

    def get_length(self) -> str:
        return f"{int(self.contest_length / 60)}"
    def __str__(self):
        return self.contest_name + str(self.contest_time) + self.contest_url + str(self.contest_length)

import requests
atc = []
url = f'https://atcoder.jp/contests/?lang=jp'
resp = requests.get(url=url, timeout=10.0)

soup = \
    BeautifulSoup(resp.text, 'lxml').find_all(name='div', attrs={'id': 'contest-table-upcoming'})[
        0].find_all(
        'tbody')[0].find_all('td')
for i in range(len(soup)):
    print(f'soup[{i}]: {soup[i]}', flush=True, end='\n')
    print(f'soup[{i}].contents: {soup[i].contents}', flush=True)

url1 = 'https://atcoder.jp' + re.findall(r'<a href="(.+?)">', str(soup[1]))[0]

contest1_name = str(soup[1].contents[3].contents[0])
print(contest1_name)
ss = str(soup[0].contents[0].contents[0].contents[0]).replace('+0900', '')
print(ss)
contest1_time1 = str(datetime.datetime.strptime(ss, '%Y-%m-%d %H:%M:%S') - datetime.timedelta(hours=1))
contest1_time = int(time.mktime(time.strptime(contest1_time1, "%Y-%m-%d %H:%M:%S")))
url1 = 'https://atcoder.jp' + re.findall(r'<a href="(.+?)">', str(soup[1]))[0]
contest1_length = re.findall(r'<td class="text-center">(.+?)</td>', str(soup[2]))[0]
length_list1 = contest1_length.split(':')

contest2_name = str(soup[5].contents[3].contents[0])
ss1 = str(soup[4].contents[0].contents[0].contents[0]).replace('+0900', '')
contest2_time2 = str(datetime.datetime.strptime(ss1, '%Y-%m-%d %H:%M:%S') - datetime.timedelta(hours=1))
contest2_time = int(time.mktime(time.strptime(contest2_time2, "%Y-%m-%d %H:%M:%S")))
url2 = 'https://atcoder.jp' + re.findall(r'<a href="(.+?)">', str(soup[5]))[0]
contest2_length: str = re.findall(r'<td class="text-center">(.+?)</td>', str(soup[6]))[0]
length_list2 = contest2_length.split(':')

atc.append(ContestType(contest1_name, contest1_time, url1, int(length_list1[0]) * 3600 + int(length_list1[1]) * 60))
atc.append(ContestType(contest2_name, contest2_time, url2, int(length_list2[0]) * 3600 + int(length_list2[1]) *60))


for contest in atc:
    print(contest)
