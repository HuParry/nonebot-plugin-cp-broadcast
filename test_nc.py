from json import loads
from html import unescape
from bs4 import BeautifulSoup, NavigableString, ResultSet, Tag
from httpx import AsyncClient, Response
from httpx._types import URLTypes, ProxiesTypes
import requests

from typing import Any, Dict, Literal, Optional, TypedDict, List, Union



url = "https://ac.nowcoder.com/acm/contest/vip-index"
content = requests.get(url).content
soup = BeautifulSoup(content, 'html.parser')
find_item: Union[Tag, NavigableString, None] = soup.find('div', class_='platform-mod js-current')
datatable: ResultSet = find_item.find_all('div', class_='platform-item js-item')
datatable2: ResultSet = find_item.find_all('a')

for contest in datatable:
    cdata: Dict[str, Any] = loads(unescape(contest.get("data-json")))
    id = unescape(contest.get("data-id"))
    cdata["contestId"] = id
    print(cdata)
