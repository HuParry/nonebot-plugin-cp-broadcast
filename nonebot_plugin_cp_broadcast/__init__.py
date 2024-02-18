from .config import Config, cp_broadcast_config
from .codeforces import *
from .nowcoder import *
from .atcoder import *
from .aiosqlite import *
import datetime
from datetime import timedelta
from nonebot.plugin import on_fullmatch
from nonebot import require, get_bot
from nonebot.rule import to_me
from nonebot.log import logger
import asyncio

cp_broadcast_list = cp_broadcast_config.cp_broadcast_list
cp_broadcast_botname = cp_broadcast_config.cp_broadcast_botname
cp_broadcast_time = cp_broadcast_config.cp_broadcast_time
cp_broadcast_updatetime = cp_broadcast_config.cp_broadcast_updatetime
cp_broadcast_cf_list = cp_broadcast_config.cp_broadcast_cf_list
cp_broadcast_cf_interval = cp_broadcast_config.cp_broadcast_cf_interval

from nonebot.plugin import PluginMetadata

__plugin_meta__ = PluginMetadata(
    name="算法竞赛比赛查询",
    description="可以查询牛客、atcoder、codeforces平台的今天和近几天的比赛信息",
    usage= \
        "cf->查询cf比赛\n" \
        "@{botname} cf查询+id->查询某人信息\n" \
        "@{botname} cf监视+id->监视某人rating变化\n" \
        "@{botname} cf监视移除+id->不再监视某人rating变化\n" \
        "@{botname} cf监视列表->展示已监视的选手id\n" \
        "@{botname} cf排名->展示已监视选手的排名\n" \
        "@{botname} cf监视备注->给某个监视选手备注\n" \
        "nc/牛客->查询牛客比赛\n" \
        "atc->查询atcoder比赛\n" \
        "today->查询今天的比赛\n" \
        "next->查询明天之后的部分比赛\n"
        "update->更新比赛数据\n" \
        "about->{botname}的一些信息\n",
    type="application",
    homepage="https://github.com/HuParry/nonebot-plugin-cp-broadcast",
    config=Config,
    supported_adapters={"nonebot.adapters.onebot.v11"},
)

try:
    scheduler = require("nonebot_plugin_apscheduler").scheduler
except BaseException:
    scheduler = None

logger.opt(colors=True).info(
    "已检测到软依赖<y>nonebot_plugin_apscheduler</y>, <g>开启定时任务功能</g>"
    if scheduler
    else "未检测到软依赖<y>nonebot_plugin_apscheduler</y>, <r>禁用定时任务功能</r>"
)


###列表下标0为比赛名称、下标1为比赛时间、下标2为比赛链接

async def ans_today():  # today
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
                msg += '比赛名称：' + each[0] + '\n' \
                       + '比赛时间：' + each[1] + '\n' \
                                                 f'比赛链接：' + each[2] + '\n'
                n = 1
            else:
                break
    n = 0
    msg2 = ''
    if len(nc) == 0:
        await get_data_nc()
    if len(nc) > 0:
        # second = '{:.3f}'.format(time.time())
        # second2 = int(float(second)*1000)
        for data in nc:
            cur_time = datetime.datetime.strptime(str(data[1]), "%Y-%m-%d %H:%M").date()
            if cur_time == today:
                if n == 0:
                    msg2 += '◉牛客比赛：\n'
                    n = 1
                msg2 += "比赛名称：" + data[0] + '\n'
                msg2 += "比赛时间：" + data[1] + '\n'
                msg2 += "比赛链接：" + data[2] + '\n'

    n = 0
    msg3 = ''

    if len(atc) == 0:
        await get_data_atc()

    if len(atc) > 0:
        for each in atc:
            cur_time = datetime.datetime.strptime(str(each[1]), "%Y-%m-%d %H:%M").date()
            if cur_time == today:
                if n == 0:
                    msg3 += '◉atc比赛：\n'
                msg3 += '比赛名称：' + each[0] + '\n' \
                        + '比赛时间：' + each[1] + '\n' \
                        + '比赛链接：' + each[2] + '\n'

    if len(cf) == 0 and len(nc) == 0 and len(atc) == 0:
        return f'查询出错了，稍后再尝试哦~'
    if msg == '' and msg2 == '' and msg3 == '':
        return '今天没有比赛，但也要好好做题哦~'
    return '找到今天的比赛如下：\n' + msg + msg2 + msg3


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
        for each in cf:
            cur_time = datetime.datetime.strptime(str(each[1]), "%Y-%m-%d %H:%M").date()
            if cur_time >= tomorrow:
                if flag == 0:
                    msg += '◉cf比赛：\n'
                    flag = 1
                msg += '比赛名称：' + each[0] + '\n' \
                       + '比赛时间：' + each[1] + '\n' \
                       + '比赛链接：' + each[2] + '\n'
                n += 1
            if n >= 2:
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
                msg2 += "比赛链接：" + data[2] + '\n'
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
                msg3 += '比赛名称：' + (each[0]) + '\n' \
                        + '比赛时间：' + (each[1]) + '\n' \
                        + '比赛链接：' + (each[2]) + '\n'

    if len(cf) == 0 and len(nc) == 0 and len(atc) == 0:
        return f'查询出错了，稍后再尝试哦~'
    if msg == '' and msg2 == '' and msg3 == '':
        return '接下来几天没有比赛，但也要好好做题哦~'
    return '找到接下来的比赛如下：\n' + msg + msg2 + msg3


today_matcher = on_fullmatch('today', priority=70, block=True)


@today_matcher.handle()
async def _():
    msg = await ans_today()
    await today_matcher.finish(msg)


next_matcher = on_fullmatch('next', priority=70, block=True)


@next_matcher.handle()
async def _():
    msg = await ans_next()
    await next_matcher.finish(msg)


help = on_fullmatch(('help', '帮助'), block=True, priority=70, rule=to_me())


@help.handle()
async def help_():
    msg = __plugin_meta__.usage.format(botname=cp_broadcast_botname)
    await help.finish(msg)


# 清晨自动播报比赛
async def auto_broadcast():
    await asyncio.sleep(1)
    for id in cp_broadcast_list:
        await asyncio.sleep(2)
        await get_bot().send_group_msg(group_id=id, message='早上好呀！' + await ans_today())


if scheduler:
    scheduler.add_job(auto_broadcast,
                      "cron", hour=cp_broadcast_time['hour'], minute=cp_broadcast_time['minute'], id="auto_broadcast"
                      )


# 凌晨12点自动更新比赛信息
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
        update, "cron", hour=cp_broadcast_updatetime['hour'], minute=cp_broadcast_updatetime['minute'], id="update"
    )

# 更新数据
update_matcher = on_fullmatch('update', priority=70, block=True)


@update_matcher.handle()
async def reply():
    await update()
    await update_matcher.finish('数据已更新完成')


# cf分数变化提醒、cf上线提醒
async def cfBroadcast():
    """
    Users = {'ratingChange': [
                {'handle': handle, 'remarks' : remarks,'oldRating': Rating.oldRating, 'newRating': Rating.newRating}
                            ],
            'cfOnline': [
                {'handle': handle, 'remarks' : remarks, 'contestId': contestId}
                            ]}
    """
    logger.info('cf监视工作开始')
    messList = await returnChangeInfo()
    logger.info('cf监视工作完成，结果已返回')

    for id in cp_broadcast_cf_list:
        await asyncio.sleep(1)
        output = f"当前时间：{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\n"
        if len(messList['ratingChange']) != 0:
            for mess in messList['ratingChange']:
                output += f"cf用户 {mess['handle']} ({mess['remarks']})分数发生变化，从 {mess['oldRating']} → {mess['newRating']}，变动了{int(mess['newRating'] - int(mess['oldRating']))}分！\n"
            await get_bot().send_group_msg(group_id=id, message=output)
            await asyncio.sleep(1)

        for mess in messList['cfOnline']:
            await get_bot().send_group_msg(group_id=id,
                                           message=f"卷王 {mess['handle']} ({mess['remarks']})又开始上cf做题啦！他在做{mess['contestId']}！\n")
            await asyncio.sleep(1)


if scheduler:
    scheduler.add_job(
        cfBroadcast, "interval", minutes=cp_broadcast_cf_interval, id="cfBroadcast"
    )
