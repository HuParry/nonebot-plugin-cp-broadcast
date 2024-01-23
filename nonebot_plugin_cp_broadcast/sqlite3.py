from .config import (cp_broadcast_path, cf_user_info_baseurl,
                     cf_user_status_baseurl, cf_user_rating_baseurl)
from nonebot.log import logger
import sqlite3
import json
import datetime
import time
from httpx import AsyncClient
from nonebot.adapters.onebot.v11 import Message, MessageSegment
import asyncio

if not cp_broadcast_path.exists():
    cp_broadcast_path.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(cp_broadcast_path / 'data.db')
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS CF_User_info (
        handle TEXT PRIMARY KEY,   
        contribution INTEGER,       
        'rank' TEXT,               
        rating INTEGER,            
        maxRank TEXT,              
        maxRanting INTEGER,        
        lastOnlineTimeSeconds INTEGER, 
        friendOfCount INTEGER,     
        avatar TEXT            
    )
"""
)
# codeforces' username
# User contribution.
# User rank, String.
# 现在的rating分
# 最高的rank
# 最高的rating分
# 上次在线时间
# The user's friend count
# 头像链接

cursor.execute("""
    CREATE TABLE IF NOT EXISTS CF_User_status (  
        handle TEXT PRIMARY KEY,   
        id INTEGER,                
        contestId INTEGER,         
        programmingLanguage TEXT,  
        passedTestCount INTEGER,   
        timeConsumedMillis INTEGER, 
        memoryConsumedBytes INTEGER 
        
    )
"""
)
#记录user的submission表
# codeforces' username
# one submission's id.
# 比赛的id
# 程序所用语言
# 通过的数据组数
# Maximum time in milliseconds, consumed by solution for one test.
# Maximum memory in bytes, consumed by solution for one test.


cursor.execute("""
    CREATE TABLE IF NOT EXISTS CF_User_rating (  
        handle TEXT PRIMARY KEY,   
        contestId INTEGER,         
        contestName TEXT,          
        'rank' INTEGER,            
        oldRating INTEGER,         
        newRating INTEGER          
    )
"""
)
#记录user的rating 变化记录，只记录最后一条
# codeforces' username
# contest's id.
# 比赛的名称
# 比赛排名
# 变化前排名
# 变化后排名

class CF_UserInfo:
    def __init__(self, handle, contribution, rank, rating, maxRank, maxRating,
                 lastOnlineTimeSeconds, friendOfCount, avatar):
        self.handle = str(handle).lower()
        self.contribution = int(contribution)
        self.rank = str(rank)
        self.rating = int(rating)
        self.maxRank = str(maxRank)
        self.maxRating = int(maxRating)
        self.lastOnlineTimeSeconds = int(lastOnlineTimeSeconds)
        self.friendOfCount = int(friendOfCount)
        self.avatar = str(avatar)

    def returnTuple(self):
        return (self.handle, self.contribution, self.rank, self.rating, self.maxRank, self.maxRating,
                    self.lastOnlineTimeSeconds, self.friendOfCount, self.avatar)

    @staticmethod
    async def getByHttp(handle: str):
        cf_user_info_url = cf_user_info_baseurl + handle
        try:
            async with AsyncClient() as client:
                response = await client.get(cf_user_info_url, timeout=10.0)
            response.raise_for_status()

            data = json.loads(response.text)
        except Exception as e:
            logger.warning(e)
            return None

        if data["status"] == "OK":
            for result in data["result"]:
                Info = CF_UserInfo(
                    handle=result["handle"],
                    contribution=result["contribution"],
                    rank=result["rank"] if result["rank"] is not None else "null",
                    rating=result["rating"] if result["rating"] is not None else 0,
                    maxRank=result["maxRank"] if result["maxRank"] is not None else "null",
                    maxRating=result["maxRating"] if result["maxRating"] is not None else 0,
                    lastOnlineTimeSeconds=result["lastOnlineTimeSeconds"] if result[
                                                                                 "lastOnlineTimeSeconds"] is not None else 0,
                    friendOfCount=result["friendOfCount"] if result["friendOfCount"] is not None else 0,
                    avatar=result["avatar"] if result["avatar"] is not None else "404"
                )

                return Info

        logger.warning('请求失败')
        return None


class CF_UserStatus:
    def __init__(self, handle, id, contestId, programmingLanguage,
                 passedTestCount, timeConsumedMillis, memoryConsumedBytes):
        self.handle = str(handle).lower()
        self.id = int(id)
        self.contestId = int(contestId)
        self.programmingLanguage = str(programmingLanguage)
        self.passedTestCount = int(passedTestCount)
        self.timeConsumedMillis = int(timeConsumedMillis)
        self.memoryConsumedBytes = int(memoryConsumedBytes)

    def returnTuple(self):
        return (self.handle, self.id, self.contestId, self.programmingLanguage,
                self.passedTestCount, self.timeConsumedMillis, self.memoryConsumedBytes)

    @staticmethod
    async def getByHttp(handle: str):
        cf_user_status_url = cf_user_status_baseurl.format(handle=handle)
        try:
            async with AsyncClient() as client:
                response = await client.get(cf_user_status_url, timeout=10.0)
            response.raise_for_status()

            data = json.loads(response.text)
        except Exception as e:
            logger.warning(e)
            return None

        if data["status"] != "OK":
            logger.warning('请求失败')
            return None

        result = data["result"][0]
        Status = CF_UserStatus(
            handle=handle,
            id=result["id"],
            contestId=result["contestId"] if result["contestId"] is not None else 0,
            programmingLanguage=result["programmingLanguage"],
            passedTestCount=result["passedTestCount"],
            timeConsumedMillis=result["timeConsumedMillis"],
            memoryConsumedBytes=result["memoryConsumedBytes"]
        )

        return Status


class CF_UserRating:
    def __init__(self, handle, contestId, contestName, rank, oldRating, newRating):
        self.handle = str(handle).lower()
        self.contestId = int(contestId)
        self.contestName = str(contestName)
        self.rank = str(rank)
        self.oldRating = int(oldRating)
        self.newRating = int(newRating)

    def returnTuple(self):
        return (self.handle, self.contestId, self.contestName,
                self.rank, self.oldRating, self.newRating)

    @staticmethod
    async def getByHttp(handle: str):
        cf_user_rating_url = cf_user_rating_baseurl.format(handle=handle)
        try:
            async with AsyncClient() as client:
                response = await client.get(cf_user_rating_url, timeout=10.0)
            response.raise_for_status()

            data = json.loads(response.text)
        except Exception as e:
            logger.warning(e)
            return None

        if data["status"] != "OK":
            logger.warning('请求失败')
            return None

        result = data["result"][-1]
        Rating = CF_UserRating(
            handle=result["handle"],
            contestId=result["contestId"],
            contestName=result["contestName"],
            rank=result["rank"],
            oldRating=result["oldRating"],
            newRating=result["newRating"]
        )

        return Rating


async def addUser(id: str):
    global conn, cursor
    Info = await CF_UserInfo.getByHttp(id)
    Status = await CF_UserStatus.getByHttp(id)
    Rating = await CF_UserRating.getByHttp(id)

    status = True

    if Info is not None:
        cursor.execute('INSERT OR REPLACE INTO CF_User_info VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', Info.returnTuple())
    else:
        status = False

    if Status is not None:
        cursor.execute('INSERT OR REPLACE INTO CF_User_status VALUES (?, ?, ?, ?, ?, ?, ?)', Status.returnTuple())
    else:
        status = False

    if Rating is not None:
        cursor.execute('INSERT OR REPLACE INTO CF_User_rating VALUES (?, ?, ?, ?, ?, ?)', Rating.returnTuple())
    else:
        status = False

    conn.commit()

    return status


async def removeUser(id: str):
    global cursor, conn

    cfid = id.lower()
    cursor.execute('DELETE FROM CF_User_info WHERE handle = ?', (cfid,))
    cursor.execute('DELETE FROM CF_User_status WHERE handle = ?', (cfid,))
    cursor.execute('DELETE FROM CF_User_rating WHERE handle = ?', (cfid,))
    conn.commit()

    if cursor.rowcount == 0:
        return False

    return True


async def returnChangeInfo():
    Users = {'ratingChange': [], 'cfOnline': []}
    global cursor, conn

    cursor.execute('SELECT CF_User_info.handle, rating, CF_User_status.id FROM CF_User_info, CF_User_status WHERE CF_User_info.handle=CF_User_status.handle')
    RS = cursor.fetchall()
    for row in RS:
        handle = row[0]
        rating = row[1]
        submission_id = row[2]

        Info = await CF_UserInfo.getByHttp(handle)
        Status = await CF_UserStatus.getByHttp(handle)
        Rating = await CF_UserRating.getByHttp(handle)

        #-----在这片区域可以写前后变化的操作
        ## 分数变化，以json形式存入
        if Rating.newRating != rating:
            Users['ratingChange'].append({'handle': handle, 'oldRating': Rating.oldRating, 'newRating': Rating.newRating})

        ## cf上线提醒，有交题说明在卷
        if Status.id != submission_id:
            Users['cfOnline'].append({'handle': handle})
        #-----

        if Info is not None:
            cursor.execute('INSERT OR REPLACE INTO CF_User_info VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', Info.returnTuple())

        if Status is not None:
            cursor.execute('INSERT OR REPLACE INTO CF_User_status VALUES (?, ?, ?, ?, ?, ?, ?)', Status.returnTuple())

        if Rating is not None:
            cursor.execute('INSERT OR REPLACE INTO CF_User_rating VALUES (?, ?, ?, ?, ?, ?)', Rating.returnTuple())

        conn.commit()

    return Users

async def returnBindList():
    list_num = 10
    global cursor, conn
    cursor.execute('SELECT handle FROM CF_User_info')
    data = cursor.fetchall()
    if data is None:
        return f'当前无监视选手'

    msg = '当前已监视选手如下:\n'

    for curTuple in data:
        msg += str(curTuple[0]) + '\n'
    return msg


async def queryUser(id: str):
    global cf_user_info_baseurl, cursor, conn
    cf_user_info_url = cf_user_info_baseurl + id

    msg = MessageSegment.text('查询失败！请检查该用户是否存在')
    try:
        async with AsyncClient() as client:
            response = await client.get(cf_user_info_url, timeout=10.0)
        response.raise_for_status()

        data = json.loads(response.text)
    except Exception as e:
        logger.warning(e)
        return msg

    if data['status'] == 'OK':
        results = data['result']

        for result in results:
            avatar_url = result['avatar'] if result["avatar"] is not None else "null"
            name = result['handle']
            rank = result['rank'] if 'rank' in result else 'Unrated'
            contest_rating = result['rating'] if 'rating' in result else '0'
            max_rating = result['maxRating'] if 'maxRating' in result else '0'
            contribution = result['contribution'] if 'contribution' in result else '0'
            friend_of = result['friendOfCount'] if 'friendOfCount' in result else '0'

            async with AsyncClient() as client:
                resp = await client.get(avatar_url, timeout=10.0)

            pic = resp.content

            msg = MessageSegment.image(pic)
            msg += Message(
                "\nname: " + name + \
                "\nrank: " + rank + \
                "\nrating: " + str(contest_rating) + \
                "\nmax rating: " + str(max_rating) + \
                "\ncontribution: " + str(contribution) + \
                "\nfriend of: " + str(friend_of) + " users"
            )

            return msg
    else:
        logger.warning('添加用户失败')
        return msg


async def returnRanklist():
    global cursor, conn
    cursor.execute('SELECT handle, rating FROM CF_User_info ORDER BY rating DESC')
    data = cursor.fetchall()
    return data
