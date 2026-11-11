"""Codeforces notifications with durable reservations for each destination."""

import asyncio
import time

from nonebot.log import logger

from .json_store import (
    ackChangeInfo, claimNotification, formatSubmissionNotice, returnChangeInfo,
)

_broadcast_running = False


def _message(kind, event):
    if kind == "cfOnline":
        return formatSubmissionNotice(event)
    return "cf用户 {} ({}) 分数发生变化，从 {} → {}，变动了 {} 分！\n".format(
        event["handle"], event["remarks"], event["oldRating"], event["newRating"],
        int(event["newRating"]) - int(event["oldRating"]),
    )


async def broadcastChanges(group_ids, send_group_msg):
    """Run at most one complete monitoring round, dropping overlapping calls."""
    global _broadcast_running
    groups = list(dict.fromkeys(str(group).strip() for group in group_ids))
    groups = [group for group in groups if group]
    if not groups:
        return
    # No await between checking and setting: concurrent coroutines on the bot's
    # event loop cannot both enter. Waiting on a lock would queue extra rounds.
    if _broadcast_running:
        logger.warning("CF监视上一轮尚未结束，跳过本次触发，不排队补跑")
        return
    started = time.monotonic()
    _broadcast_running = True
    try:
        await _broadcast_once(groups, send_group_msg)
    finally:
        _broadcast_running = False
        logger.info("CF监视本轮结束，耗时 {:.1f} 秒".format(time.monotonic() - started))


async def _broadcast_once(groups, send_group_msg):
    changes = await returnChangeInfo()
    for group in groups:
        for kind in ("ratingChange", "cfOnline"):
            # Rating watermarks must be reserved in increasing event order.
            events = sorted(changes[kind], key=lambda event: (
                int(event["ratingUpdateTimeSeconds"]), int(event["contestId"])
            )) if kind == "ratingChange" else changes[kind]
            for event in events:
                try:
                    message = _message(kind, event)
                    if not await claimNotification(group, kind, event):
                        continue
                except Exception:
                    logger.exception("CF通知去重状态无法保存，跳过发送：group={} handle={}".format(
                        group, event["handle"]
                    ))
                    continue
                try:
                    await send_group_msg(group_id=group, message=message)
                except Exception:
                    logger.exception("CF通知发送失败或结果不明，已保留去重记录，不自动重发：group={} handle={}".format(
                        group, event["handle"]
                    ))
                else:
                    confirmed = {"ratingChange": [], "cfOnline": []}
                    confirmed[kind] = [event]
                    try:
                        await ackChangeInfo(confirmed)
                    except Exception:
                        logger.exception("CF通知确认写入失败，发送前去重记录仍有效：group={} handle={}".format(
                            group, event["handle"]
                        ))
                await asyncio.sleep(1)
