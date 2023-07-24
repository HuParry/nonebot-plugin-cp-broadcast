from .config import cp_broadcast_path, cf_user_info_baseurl
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
    CREATE TABLE IF NOT EXISTS CF_User (
        id TEXT PRIMARY KEY,
        now_rating INTEGER,
        update_time INTEGER,
        QQ INTEGER,
        status INTEGER,
        last_rating INTEGER,
        avatar_url TEXT
    )
"""
)

class CF_UserType:
    def __init__(self, id, now_rating, update_time, QQ, status, last_rating, avatar_url):
        self.id = id
        self.now_rating = now_rating if now_rating is not None else 0                  # cf上次上线时间
        self.update_time = update_time if update_time is not None else 0
        self.QQ = QQ if QQ is not None else 0
        self.status = status if status is not None else 1
        self.last_rating = last_rating if last_rating is not None else 0
        self.avatar_url = avatar_url

async def addUser(id: str, QQ: int):
    global cf_user_info_baseurl, cursor, conn
    cf_user_info_url = cf_user_info_baseurl + id

    try:
        async with AsyncClient() as client:
            response = await client.get(cf_user_info_url, timeout=10.0)
        response.raise_for_status()

        data = json.loads(response.text)
    except Exception as e:
        logger.warning(e)
        return False
    
    if data['status'] == 'OK':
        results = data['result']

        for result in results:
            update_time = int(result["lastOnlineTimeSeconds"])
            user = CF_UserType(result["handle"], result["rating"], update_time, QQ, 1, result["rating"], result["avatar"])
            cursor.execute('''
            INSERT OR REPLACE INTO CF_User (id, now_rating, update_time,QQ,status,last_rating,avatar_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
                user.id,
                user.now_rating,
                user.update_time,
                user.QQ,
                user.status,
                user.last_rating,
                user.avatar_url
            ))
            conn.commit()
            return True
    else:
        logger.warning('添加用户失败')
        return False
    
async def removeUser(id: str):
    global cf_user_info_baseurl, cursor, conn
    cf_user_info_url = cf_user_info_baseurl + id

    try:
        async with AsyncClient() as client:
            response = await client.get(cf_user_info_url, timeout=10.0)
        response.raise_for_status()

        user_data = json.loads(response.text)
    except Exception as e:
        logger.warning(e)
        return False
    
    cfid = ''
    if user_data['status'] == 'OK':
        resluts = user_data['result']

        for reslut in resluts:
            cfid = str(reslut['handle'])
    else:
        logger.warning(f"cf api查询状态为{user_data['status']}")
        return False

    conn.execute('SELECT * FROM CF_User WHERE id = ?', (cfid,))
    data = cursor.fetchall()
    if data is None:
        logger.warning(f'监视成员中没有此人:{cfid}')
        return False
    
    conn.execute('DELETE FROM CF_User WHERE id = ?', (cfid,))
    conn.commit()

    return True
        
async def updateUser():
    Users = {'ratingChange' : [], 'cfOnline' : []}
    global cf_user_info_baseurl, cursor, conn

    cursor.execute('SELECT * FROM CF_User')
    RS = cursor.fetchall()
    for row in RS:
        Oid, Onow_rating, Oupdate_time, OQQ, Ostatus, Olast_rating, Oavatar_url = row
        user_info_url = cf_user_info_baseurl + Oid
        await asyncio.sleep(0.3)
        try:
            async with AsyncClient() as client:
                response = await client.get(user_info_url, timeout=10.0)
            response.raise_for_status() 
            data = json.loads(response.text)
        except Exception as e:
            logger.warning(e)
            continue

        if data["status"] == "OK":
            # 获取result列表
            results = data["result"]
            
            # 遍历每个结果并储存键值
            for result in results:
                update_time = int(result["lastOnlineTimeSeconds"])

                if update_time != Oupdate_time:
                    Users['cfOnline'].append(str(Oid))

                user = CF_UserType(Oid, result["rating"], update_time, OQQ, Ostatus, Onow_rating, result["avatar"])
                Users['ratingChange'].append(user)

                cursor.execute('''
                INSERT OR REPLACE INTO CF_User (id, now_rating, update_time,QQ,status,last_rating,avatar_url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                user.id,
                user.now_rating,
                user.update_time,
                user.QQ,
                user.status,
                user.last_rating,
                user.avatar_url
            ))
                conn.commit()
        else:
            logger.warning("数据请求失败")

    return Users

async def returChangeInfo():
    outputlist = {'ratingChange' : [], 'cfOnline' : []}
    Users = await updateUser()

    global cursor, conn
    for user in Users['ratingChange']:
        output=f"当前时间：{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\n"
        cursor.execute('SELECT now_rating,last_rating,QQ FROM CF_User WHERE id = ?', (user.id,))
        row = cursor.fetchone()
        now_rating, last_rating, QQ = row
        if last_rating != now_rating:
            change = now_rating - last_rating
            output += f"cf用户 {user.id} 分数发生变化，从 {last_rating} → {now_rating}，变动了{change}分！\n"
            outputlist['ratingChange'].append(output)

    for id in Users['cfOnline']:
        ouput = f'卷王 {id} 又开始上cf做题啦！'
        outputlist['cfOnline'].append(ouput)

    return outputlist


async def returnBindList():
    global cursor, conn
    cursor.execute('SELECT id FROM CF_User')
    data = cursor.fetchall()
    if data is None:
        return f'当前无监视选手'

    msg = '当前已监视选手如下:\n'
    
    for i in range(0, 10 if len(data) >= 10 else len(data)):
        curTuple = data[i]
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
            avatar_url = result['avatar']
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