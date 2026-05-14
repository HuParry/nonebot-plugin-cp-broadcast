from .config import (cp_broadcast_path, cf_user_info_baseurl,
                     cf_user_status_baseurl, cf_user_rating_baseurl)
from nonebot.log import logger
import aiosqlite
import json
import datetime
import time
from httpx import AsyncClient
from nonebot.adapters.onebot.v11 import Message, MessageSegment
import asyncio
from nonebot import get_driver

driver = get_driver()

conn: aiosqlite.Connection
cursor: aiosqlite.Cursor


@driver.on_startup
async def _on_startup():
    if not cp_broadcast_path.exists():
        cp_broadcast_path.mkdir(parents=True, exist_ok=True)

    global conn, cursor
    conn = await aiosqlite.connect(cp_broadcast_path / 'data.db')
    cursor = await conn.cursor()
    await cursor.execute("""
        CREATE TABLE IF NOT EXISTS CF_User (
            handle                       TEXT    PRIMARY KEY,
            contribution                 INTEGER DEFAULT 0,
            rank                         TEXT    DEFAULT 'unrated',
            rating                       INTEGER DEFAULT 0,
            max_rank                     TEXT    DEFAULT 'unrated',
            max_rating                   INTEGER DEFAULT 0,
            last_online_time             INTEGER DEFAULT 0,
            friend_of_count              INTEGER DEFAULT 0,
            avatar                       TEXT    DEFAULT '',
            last_submission_id           INTEGER DEFAULT 0,
            last_submission_contest_id   INTEGER DEFAULT 0,
            last_submission_language     TEXT    DEFAULT '',
            last_submission_passed_tests INTEGER DEFAULT 0,
            last_submission_time_ms      INTEGER DEFAULT 0,
            last_submission_memory_bytes INTEGER DEFAULT 0,
            last_rated_contest_id        INTEGER DEFAULT 0,
            last_rated_contest_name      TEXT    DEFAULT '',
            last_rated_rank              INTEGER DEFAULT 0,
            last_rated_old_rating        INTEGER DEFAULT 0,
            last_rated_new_rating        INTEGER DEFAULT 0,
            remarks                      TEXT    DEFAULT '',
            broadcast_time               INTEGER DEFAULT 0
        )
    """)
    await conn.commit()


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

    @staticmethod
    async def getByHttp(handle: str):
        cf_user_info_url = cf_user_info_baseurl + handle
        try:
            await asyncio.sleep(0.5)
            async with AsyncClient() as client:
                response = await client.get(cf_user_info_url, timeout=10.0)
            response.raise_for_status()
            data = json.loads(response.text)
        except Exception as e:
            logger.warning(e)
            return None

        if data["status"] == "OK":
            for result in data["result"]:
                return CF_UserInfo(
                    handle=result["handle"],
                    contribution=result["contribution"],
                    rank=result.get("rank", "null"),
                    rating=result.get("rating", 0),
                    maxRank=result.get("maxRank", "null"),
                    maxRating=result.get("maxRating", 0),
                    lastOnlineTimeSeconds=result.get("lastOnlineTimeSeconds", 0),
                    friendOfCount=result.get("friendOfCount", 0),
                    avatar=result.get("avatar", "404"),
                )

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

    @staticmethod
    async def getByHttp(handle: str):
        cf_user_status_url = cf_user_status_baseurl.format(handle=handle)
        try:
            await asyncio.sleep(0.5)
            async with AsyncClient() as client:
                response = await client.get(cf_user_status_url, timeout=10.0)
            response.raise_for_status()
            data = json.loads(response.text)
        except Exception as e:
            logger.warning(e)
            return None

        if data["status"] != "OK" or len(data["result"]) == 0:
            return None

        result = data["result"][0]
        return CF_UserStatus(
            handle=handle,
            id=result["id"],
            contestId=result.get("contestId", 0),
            programmingLanguage=result["programmingLanguage"],
            passedTestCount=result["passedTestCount"],
            timeConsumedMillis=result["timeConsumedMillis"],
            memoryConsumedBytes=result["memoryConsumedBytes"],
        )


class CF_UserRating:
    def __init__(self, handle, contestId, contestName, rank, oldRating, newRating):
        self.handle = str(handle).lower()
        self.contestId = int(contestId)
        self.contestName = str(contestName)
        self.rank = int(rank)
        self.oldRating = int(oldRating)
        self.newRating = int(newRating)

    @staticmethod
    async def getByHttp(handle: str):
        cf_user_rating_url = cf_user_rating_baseurl.format(handle=handle)
        try:
            await asyncio.sleep(0.5)
            async with AsyncClient() as client:
                response = await client.get(cf_user_rating_url, timeout=10.0)
            response.raise_for_status()
            data = json.loads(response.text)
        except Exception as e:
            logger.warning(e)
            return None

        if data["status"] != "OK" or len(data["result"]) == 0:
            return None

        result = data["result"][-1]
        return CF_UserRating(
            handle=result["handle"],
            contestId=result["contestId"],
            contestName=result["contestName"],
            rank=result["rank"],
            oldRating=result["oldRating"],
            newRating=result["newRating"],
        )


async def addUser(id: str):
    global conn, cursor
    Info = await CF_UserInfo.getByHttp(id)
    Status = await CF_UserStatus.getByHttp(id)
    Rating = await CF_UserRating.getByHttp(id)

    if Info is None:
        return False

    await cursor.execute('''
        INSERT OR REPLACE INTO CF_User (
            handle, contribution, rank, rating, max_rank, max_rating,
            last_online_time, friend_of_count, avatar,
            last_submission_id, last_submission_contest_id, last_submission_language,
            last_submission_passed_tests, last_submission_time_ms, last_submission_memory_bytes,
            last_rated_contest_id, last_rated_contest_name, last_rated_rank,
            last_rated_old_rating, last_rated_new_rating,
            remarks, broadcast_time
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        Info.handle, Info.contribution, Info.rank, Info.rating,
        Info.maxRank, Info.maxRating, Info.lastOnlineTimeSeconds,
        Info.friendOfCount, Info.avatar,
        Status.id if Status else 0,
        Status.contestId if Status else 0,
        Status.programmingLanguage if Status else '',
        Status.passedTestCount if Status else 0,
        Status.timeConsumedMillis if Status else 0,
        Status.memoryConsumedBytes if Status else 0,
        Rating.contestId if Rating else 0,
        Rating.contestName if Rating else '',
        Rating.rank if Rating else 0,
        Rating.oldRating if Rating else 0,
        Rating.newRating if Rating else 0,
        Info.handle,  # remarks 默认为 handle
        0,
    ))
    await conn.commit()
    return True


async def removeUser(id: str):
    global cursor, conn
    await cursor.execute('DELETE FROM CF_User WHERE handle = ?', (id.lower(),))
    deleted = cursor.rowcount
    await conn.commit()
    return deleted > 0


async def returnChangeInfo():
    Users = {'ratingChange': [], 'cfOnline': []}
    global cursor, conn

    await cursor.execute('''
        SELECT handle, rating, last_submission_id, remarks, broadcast_time
        FROM CF_User
    ''')
    RS = await cursor.fetchall()

    for row in RS:
        handle = row[0]
        cached_rating = row[1]
        cached_submission_id = row[2]
        remarks = row[3]
        broadcast_time = int(row[4])

        Info = await CF_UserInfo.getByHttp(handle)
        Status = await CF_UserStatus.getByHttp(handle)
        Rating = await CF_UserRating.getByHttp(handle)

        if Rating is not None and Rating.newRating != cached_rating:
            Users['ratingChange'].append({
                'handle': handle, 'remarks': remarks,
                'oldRating': Rating.oldRating, 'newRating': Rating.newRating,
            })

        if (Status is not None and Status.id != cached_submission_id and
                (int(time.time()) - broadcast_time >= 7200)):
            await cursor.execute(
                'UPDATE CF_User SET broadcast_time = ? WHERE handle = ?',
                (int(time.time()), handle)
            )
            Users['cfOnline'].append({'handle': handle, 'remarks': remarks, 'contestId': Status.contestId})

        if Info is not None:
            await cursor.execute('''
                UPDATE CF_User SET
                    contribution = ?, rank = ?, rating = ?, max_rank = ?, max_rating = ?,
                    last_online_time = ?, friend_of_count = ?, avatar = ?
                WHERE handle = ?
            ''', (Info.contribution, Info.rank, Info.rating, Info.maxRank, Info.maxRating,
                  Info.lastOnlineTimeSeconds, Info.friendOfCount, Info.avatar, handle))

        if Status is not None:
            await cursor.execute('''
                UPDATE CF_User SET
                    last_submission_id = ?, last_submission_contest_id = ?,
                    last_submission_language = ?, last_submission_passed_tests = ?,
                    last_submission_time_ms = ?, last_submission_memory_bytes = ?
                WHERE handle = ?
            ''', (Status.id, Status.contestId, Status.programmingLanguage,
                  Status.passedTestCount, Status.timeConsumedMillis,
                  Status.memoryConsumedBytes, handle))

        if Rating is not None:
            await cursor.execute('''
                UPDATE CF_User SET
                    last_rated_contest_id = ?, last_rated_contest_name = ?, last_rated_rank = ?,
                    last_rated_old_rating = ?, last_rated_new_rating = ?
                WHERE handle = ?
            ''', (Rating.contestId, Rating.contestName, Rating.rank,
                  Rating.oldRating, Rating.newRating, handle))

        await conn.commit()

    return Users


async def returnBindList():
    global cursor, conn
    await cursor.execute('SELECT handle, remarks FROM CF_User')
    data = await cursor.fetchall()
    if not data:
        return '当前无监视选手'

    msg = '当前已监视选手如下:\n'
    for row in data:
        msg += f'{row[0]}({row[1]}) \n'
    return msg


async def queryUser(id: str):
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
        for result in data['result']:
            avatar_url = result.get('avatar', 'null')
            name = result['handle']
            rank = result.get('rank', 'Unrated')
            contest_rating = result.get('rating', '0')
            max_rating = result.get('maxRating', '0')
            contribution = result.get('contribution', '0')
            friend_of = result.get('friendOfCount', '0')

            async with AsyncClient() as client:
                resp = await client.get(avatar_url, timeout=10.0)

            msg = MessageSegment.image(resp.content)
            msg += Message(
                "\nname: " + name +
                "\nrank: " + rank +
                "\nrating: " + str(contest_rating) +
                "\nmax rating: " + str(max_rating) +
                "\ncontribution: " + str(contribution) +
                "\nfriend of: " + str(friend_of) + " users"
            )
            return msg
    else:
        logger.warning('添加用户失败')
        return msg


async def returnRanklist():
    global cursor, conn
    await cursor.execute('SELECT handle, rating FROM CF_User ORDER BY rating DESC')
    return await cursor.fetchall()


async def modifyRemarks(cf_id: str, cf_remarks: str):
    global cursor, conn
    await cursor.execute(
        'UPDATE CF_User SET remarks = ? WHERE handle = ?',
        (cf_remarks, cf_id.lower())
    )
    await conn.commit()
    return cursor.rowcount > 0
