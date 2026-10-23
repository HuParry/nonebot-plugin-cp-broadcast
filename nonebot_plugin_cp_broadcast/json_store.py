"""Codeforces API data and monitor state stored in a readable JSON file."""

import asyncio
import copy
import json
import os
import tempfile
import time
from typing import List

from httpx import AsyncClient
from nonebot import get_driver
from nonebot.adapters.onebot.v11 import Message, MessageSegment
from nonebot.log import logger

from .config import (
    cp_broadcast_path,
    cf_user_info_baseurl,
    cf_user_status_baseurl,
    cf_user_rating_baseurl,
)

driver = get_driver()
JSON_PATH = cp_broadcast_path / "data.json"
_store = {"version": 1, "users": {}}
_store_lock = None
_api_lock = None
_last_api_request_at = None
_data_lock_file = None

__all__ = [
    "CF_UserInfo",
    "CF_UserStatus",
    "CF_UserRating",
    "addUser",
    "removeUser",
    "returnChangeInfo",
    "ackChangeInfo",
    "claimNotification",
    "formatSubmissionNotice",
    "requestCodeforces",
    "returnBindList",
    "queryUser",
    "returnRanklist",
    "modifyRemarks",
]

def _empty_store():
    return {"version": 1, "users": {}}


def _optional_int(value):
    return int(value) if value is not None else None


def _optional_text(value):
    return str(value) if value is not None else None


async def requestCodeforces(url):
    """Serialize API calls and respect Codeforces' two-second rate limit."""
    global _api_lock, _last_api_request_at
    if _api_lock is None:
        _api_lock = asyncio.Lock()
    async with _api_lock:
        async with AsyncClient() as client:
            if _last_api_request_at is not None:
                wait = 2.1 - (time.monotonic() - _last_api_request_at)
                if wait > 0:
                    await asyncio.sleep(wait)
            _last_api_request_at = time.monotonic()
            response = await client.get(url, timeout=10.0)
        response.raise_for_status()
        data = json.loads(response.text)
        if not isinstance(data, dict):
            raise ValueError("Codeforces API 响应必须是 JSON 对象")
        return data


def _atomic_write_json(data):
    cp_broadcast_path.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".data-", suffix=".tmp", dir=str(cp_broadcast_path)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(data, output, ensure_ascii=False, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_name, str(JSON_PATH))
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def _validate_store(data):
    if not isinstance(data, dict):
        raise ValueError("data.json 根节点必须是 JSON 对象")
    if data.get("version") != 1:
        raise ValueError("不支持的 data.json 版本：{}".format(data.get("version")))
    if not isinstance(data.get("users"), dict):
        raise ValueError("data.json 的 users 必须是 JSON 对象")

    normalized_data = copy.deepcopy(data)
    normalized_users = {}
    for handle, user in normalized_data["users"].items():
        normalized_handle = str(handle).lower()
        if normalized_handle in normalized_users:
            raise ValueError("data.json 中存在重复的 handle：{}".format(normalized_handle))
        if not isinstance(user, dict):
            raise ValueError("data.json 中用户 {} 的值必须是对象".format(handle))
        user.setdefault("profile", {})
        user.setdefault("monitor", {})
        user.setdefault("rating_history", {})
        if not isinstance(user["profile"], dict):
            raise ValueError("用户 {} 的 profile 必须是 JSON 对象".format(handle))
        if not isinstance(user["monitor"], dict):
            raise ValueError("用户 {} 的 monitor 必须是 JSON 对象".format(handle))
        if not isinstance(user["rating_history"], dict):
            raise ValueError("用户 {} 的 rating_history 必须是 JSON 对象".format(handle))
        user["rating_history"] = _latest_five_stored_ratings(user["rating_history"])
        normalized_users[normalized_handle] = user
    normalized_data["users"] = normalized_users
    return normalized_data


def _stored_rating_sort_key(item):
    key, value = item
    if not isinstance(value, dict):
        return (-1, -1, str(key))
    try:
        update_time = int(value.get("rating_update_time_seconds", -1))
    except (TypeError, ValueError):
        update_time = -1
    try:
        contest_id = int(value.get("contest_id", key))
    except (TypeError, ValueError):
        contest_id = -1
    return (update_time, contest_id, str(key))


def _latest_five_stored_ratings(history):
    """Return at most the five most recent stored rating records."""
    return dict(sorted(history.items(), key=_stored_rating_sort_key)[-5:])


def _acquire_data_directory_lock():
    """Refuse a second writer rather than letting stale processes resend data."""
    global _data_lock_file
    if _data_lock_file is not None:
        return
    lock_file = (cp_broadcast_path / ".cp-broadcast.lock").open("a+b")
    try:
        if os.name == "nt":
            import msvcrt
            if os.fstat(lock_file.fileno()).st_size == 0:
                lock_file.write(b"0")
                lock_file.flush()
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception as error:
        lock_file.close()
        raise RuntimeError("Codeforces 数据目录已被其他进程占用或无法加锁：{}".format(
            cp_broadcast_path
        )) from error
    _data_lock_file = lock_file


def _release_data_directory_lock():
    global _data_lock_file
    if _data_lock_file is not None:
        _data_lock_file.close()
        _data_lock_file = None


@driver.on_shutdown
async def _on_shutdown():
    _release_data_directory_lock()


@driver.on_startup
async def _on_startup():
    global _store, _store_lock
    _store_lock = asyncio.Lock()
    cp_broadcast_path.mkdir(parents=True, exist_ok=True)
    _acquire_data_directory_lock()
    logger.info("CF监视：已启用按群持久化去重（发送前预留，失败不自动重发），数据文件：{}".format(JSON_PATH))
    if JSON_PATH.exists():
        try:
            with JSON_PATH.open("r", encoding="utf-8") as source:
                loaded_store = json.load(source)
            normalized_store = _validate_store(loaded_store)
        except Exception as error:
            # Preserve a malformed/unknown file instead of silently replacing it.
            raise RuntimeError("无法读取 Codeforces JSON 数据文件 {}".format(JSON_PATH)) from error
        if normalized_store != loaded_store:
            try:
                _atomic_write_json(normalized_store)
            except Exception as error:
                raise RuntimeError("无法写入规范化后的 Codeforces JSON 数据文件 {}".format(JSON_PATH)) from error
        _store = normalized_store
        return

    _store = _empty_store()
    _atomic_write_json(_store)
    logger.info("已创建 Codeforces JSON 数据文件：{}".format(JSON_PATH))


class CF_UserInfo:
    def __init__(self, handle, contribution=None, rank=None, rating=None,
                 maxRank=None, maxRating=None, lastOnlineTimeSeconds=None,
                 friendOfCount=None, avatar=None, titlePhoto=None,
                 firstName=None, lastName=None, country=None, city=None,
                 organization=None, registrationTimeSeconds=None):
        self.handle = str(handle).lower()
        self.firstName = _optional_text(firstName)
        self.lastName = _optional_text(lastName)
        self.country = _optional_text(country)
        self.city = _optional_text(city)
        self.organization = _optional_text(organization)
        self.contribution = _optional_int(contribution)
        self.rank = _optional_text(rank)
        self.rating = _optional_int(rating)
        self.maxRank = _optional_text(maxRank)
        self.maxRating = _optional_int(maxRating)
        self.lastOnlineTimeSeconds = _optional_int(lastOnlineTimeSeconds)
        self.registrationTimeSeconds = _optional_int(registrationTimeSeconds)
        self.friendOfCount = _optional_int(friendOfCount)
        self.avatar = _optional_text(avatar)
        self.titlePhoto = _optional_text(titlePhoto)

    @staticmethod
    async def getByHttp(handle: str):
        url = cf_user_info_baseurl + handle
        try:
            data = await requestCodeforces(url)
        except Exception as error:
            logger.warning(error)
            return None

        if data.get("status") == "OK" and data.get("result"):
            result = data["result"][0]
            return CF_UserInfo(
                handle=result["handle"],
                firstName=result.get("firstName"),
                lastName=result.get("lastName"),
                country=result.get("country"),
                city=result.get("city"),
                organization=result.get("organization"),
                contribution=result.get("contribution"),
                rank=result.get("rank"),
                rating=result.get("rating"),
                maxRank=result.get("maxRank"),
                maxRating=result.get("maxRating"),
                lastOnlineTimeSeconds=result.get("lastOnlineTimeSeconds"),
                registrationTimeSeconds=result.get("registrationTimeSeconds"),
                friendOfCount=result.get("friendOfCount"),
                avatar=result.get("avatar"),
                titlePhoto=result.get("titlePhoto"),
            )

        logger.warning("请求 Codeforces 用户资料失败")
        return None


class CF_UserStatus:
    def __init__(self, handle, id, contestId=None, creationTimeSeconds=None):
        self.handle = str(handle).lower()
        self.id = int(id)
        self.contestId = _optional_int(contestId)
        self.creationTimeSeconds = _optional_int(creationTimeSeconds)

    @staticmethod
    async def getByHttp(handle: str):
        url = cf_user_status_baseurl.format(handle=handle)
        try:
            data = await requestCodeforces(url)
            if data.get("status") != "OK":
                logger.warning("请求 Codeforces 提交记录失败：{}".format(data.get("comment")))
                return None
            result = data["result"]
            if not isinstance(result, list):
                raise ValueError("Codeforces 提交记录 result 必须是列表")
            # Zero is a successful empty history; None means the request failed.
            if not result:
                return CF_UserStatus(handle=handle, id=0)
            submission = result[0]
            status = CF_UserStatus(
                handle=handle,
                id=submission["id"],
                contestId=submission.get("contestId"),
                creationTimeSeconds=submission["creationTimeSeconds"],
            )
            if status.id <= 0:
                raise ValueError("Codeforces 提交 ID 必须大于零")
            return status
        except Exception as error:
            logger.warning(error)
            return None


class CF_UserRating:
    def __init__(self, handle, contestId, contestName, rank, oldRating,
                 newRating, ratingUpdateTimeSeconds):
        self.handle = str(handle).lower()
        self.contestId = int(contestId)
        self.contestName = str(contestName)
        self.rank = int(rank)
        self.oldRating = int(oldRating)
        self.newRating = int(newRating)
        self.ratingUpdateTimeSeconds = int(ratingUpdateTimeSeconds)

    @staticmethod
    def _from_result(result):
        return CF_UserRating(
            handle=result["handle"],
            contestId=result["contestId"],
            contestName=result["contestName"],
            rank=result["rank"],
            oldRating=result["oldRating"],
            newRating=result["newRating"],
            ratingUpdateTimeSeconds=result["ratingUpdateTimeSeconds"],
        )

    @staticmethod
    async def getAllByHttp(handle: str):
        url = cf_user_rating_baseurl.format(handle=handle)
        try:
            data = await requestCodeforces(url)
        except Exception as error:
            logger.warning(error)
            return None

        if data.get("status") != "OK":
            logger.warning("请求 Codeforces rating 历史失败")
            return None
        return [CF_UserRating._from_result(row) for row in data.get("result", [])]

    @staticmethod
    async def getByHttp(handle: str):
        """Return the latest event for callers that only need one rating row."""
        history = await CF_UserRating.getAllByHttp(handle)
        return history[-1] if history else None


def _profile_data(info: CF_UserInfo, fetched_at_seconds: int):
    return {
        "handle": info.handle,
        "first_name": info.firstName,
        "last_name": info.lastName,
        "country": info.country,
        "city": info.city,
        "organization": info.organization,
        "contribution": info.contribution,
        "rank": info.rank,
        "rating": info.rating,
        "max_rank": info.maxRank,
        "max_rating": info.maxRating,
        "last_online_time_seconds": info.lastOnlineTimeSeconds,
        "registration_time_seconds": info.registrationTimeSeconds,
        "friend_of_count": info.friendOfCount,
        "avatar": info.avatar,
        "title_photo": info.titlePhoto,
        "fetched_at_seconds": fetched_at_seconds,
    }


def _rating_data(rating: CF_UserRating):
    return {
        "contest_id": rating.contestId,
        "contest_name": rating.contestName,
        "rank": rating.rank,
        "rating_update_time_seconds": rating.ratingUpdateTimeSeconds,
        "old_rating": rating.oldRating,
        "new_rating": rating.newRating,
    }


def _replace_history(user_data: dict, history: List[CF_UserRating]):
    """Replace persisted history with the five most recent API records."""
    recent_ratings = sorted(
        history,
        key=lambda item: (item.ratingUpdateTimeSeconds, item.contestId),
    )[-5:]
    replacement = {
        str(rating.contestId): _rating_data(rating)
        for rating in recent_ratings
    }
    changed = user_data.get("rating_history", {}) != replacement
    user_data["rating_history"] = replacement
    return changed


async def addUser(id: str):
    info = await CF_UserInfo.getByHttp(id)
    if info is None:
        return False

    status = await CF_UserStatus.getByHttp(info.handle)
    rating_history = await CF_UserRating.getAllByHttp(info.handle)
    now = int(time.time())
    latest_rating = max(
        rating_history or [],
        key=lambda item: (item.ratingUpdateTimeSeconds, item.contestId),
        default=None,
    )
    # If the rating endpoint is unavailable at registration, use a current
    # baseline to avoid announcing all old rating events on the next poll.
    rating_cursor_time = latest_rating.ratingUpdateTimeSeconds if latest_rating else now
    rating_cursor_contest = latest_rating.contestId if latest_rating else 2147483647

    async with _store_lock:
        candidate = copy.deepcopy(_store)
        users = candidate["users"]
        user_data = users.get(info.handle)
        if user_data is None:
            user_data = {
                "profile": {},
                "monitor": {
                    "remarks": info.handle,
                    "created_at_seconds": now,
                    "last_processed_submission_id": status.id if status is not None else None,
                    "last_notified_submission_id": 0,
                    "last_submission_event_at_seconds": 0,
                    "last_submission_notice_at_seconds": 0,
                    "last_notified_rating_update_time_seconds": rating_cursor_time,
                    "last_notified_rating_contest_id": rating_cursor_contest,
                },
                "rating_history": {},
            }
            users[info.handle] = user_data
        user_data["profile"] = _profile_data(info, now)
        if rating_history is not None:
            _replace_history(user_data, rating_history)
        _commit_store(candidate)
    return True


def _commit_store(candidate):
    global _store
    if _data_lock_file is None:
        raise RuntimeError("未持有 Codeforces 数据目录锁，拒绝写入通知状态")
    _atomic_write_json(candidate)
    _store = candidate


async def removeUser(id: str):
    handle = id.lower()
    async with _store_lock:
        if handle not in _store["users"]:
            return False
        candidate = copy.deepcopy(_store)
        del candidate["users"][handle]
        _commit_store(candidate)
    return True


async def returnChangeInfo():
    users = {"ratingChange": [], "cfOnline": []}
    async with _store_lock:
        handles = list(_store["users"].keys())

    fetched = []
    for handle in handles:
        info = await CF_UserInfo.getByHttp(handle)
        status = await CF_UserStatus.getByHttp(handle)
        rating_history = await CF_UserRating.getAllByHttp(handle)
        fetched.append((handle, info, status, rating_history))

    now = int(time.time())
    async with _store_lock:
        candidate = copy.deepcopy(_store)
        dirty = False

        for handle, info, status, rating_history in fetched:
            user_data = candidate["users"].get(handle)
            # A user may have been removed while the API requests were running.
            if user_data is None:
                continue
            monitor = user_data["monitor"]
            remarks = monitor.get("remarks", handle)

            if info is not None:
                user_data["profile"] = _profile_data(info, now)
                dirty = True
            if rating_history is not None:
                dirty = _replace_history(user_data, rating_history) or dirty

            if rating_history is not None:
                rating_cursor = (
                    monitor.get("last_notified_rating_update_time_seconds"),
                    monitor.get("last_notified_rating_contest_id"),
                )
                cursor_pair = (
                    int(rating_cursor[0]) if rating_cursor[0] is not None else -1,
                    int(rating_cursor[1]) if rating_cursor[1] is not None else -1,
                )
                new_events = [
                    item for item in rating_history
                    if (item.ratingUpdateTimeSeconds, item.contestId) > cursor_pair
                ]
                new_events.sort(
                    key=lambda item: (item.ratingUpdateTimeSeconds, item.contestId)
                )
                for item in new_events:
                    users["ratingChange"].append({
                        "handle": handle,
                        "remarks": remarks,
                        "oldRating": item.oldRating,
                        "newRating": item.newRating,
                        "contestId": item.contestId,
                        "contestName": item.contestName,
                        "ratingUpdateTimeSeconds": item.ratingUpdateTimeSeconds,
                    })

            processed_id = monitor.get("last_processed_submission_id")
            last_event_at = int(monitor.get("last_submission_event_at_seconds", 0) or 0)
            if status is None:
                continue
            if processed_id is None:
                # An unavailable endpoint at registration must not turn the
                # first successful response into an announcement of old activity.
                monitor["last_processed_submission_id"] = status.id
                dirty = True
                continue
            # Zero represents an empty result, not a submission. Compare real
            # submission IDs for equality only; their magnitude is irrelevant.
            if status.id == 0 or status.id == int(processed_id):
                continue
            # Consume the newly observed ID in this polling transaction,
            # independently of notification delivery or acknowledgement.
            # The transaction must reach disk before any events are returned.
            monitor["last_processed_submission_id"] = status.id
            dirty = True
            if last_event_at and (
                now - last_event_at < 7200 or
                (status.creationTimeSeconds is not None and
                 status.creationTimeSeconds < last_event_at + 7200)
            ):
                continue
            # Start cooldown when creating the event, even if sending fails.
            monitor["last_submission_event_at_seconds"] = now
            users["cfOnline"].append({
                "handle": handle,
                "remarks": remarks,
                "contestId": status.contestId,
                "submissionId": status.id,
                "creationTimeSeconds": status.creationTimeSeconds,
            })

        if dirty:
            _commit_store(candidate)

    return users


async def ackChangeInfo(users):
    """Record confirmed sends; durable per-group claims provide deduplication."""
    now = int(time.time())
    async with _store_lock:
        candidate = copy.deepcopy(_store)
        dirty = False
        rating_cursors = {}
        for event in users["ratingChange"]:
            handle = event["handle"]
            pair = (int(event["ratingUpdateTimeSeconds"]), int(event["contestId"]))
            if handle not in rating_cursors or pair > rating_cursors[handle]:
                rating_cursors[handle] = pair

        for handle, (rating_time, contest_id) in rating_cursors.items():
            user_data = candidate["users"].get(handle)
            if user_data is None:
                continue
            monitor = user_data["monitor"]
            previous = (
                monitor.get("last_notified_rating_update_time_seconds"),
                monitor.get("last_notified_rating_contest_id"),
            )
            previous_pair = (
                int(previous[0]) if previous[0] is not None else -1,
                int(previous[1]) if previous[1] is not None else -1,
            )
            if (rating_time, contest_id) > previous_pair:
                monitor["last_notified_rating_update_time_seconds"] = rating_time
                monitor["last_notified_rating_contest_id"] = contest_id
                dirty = True

        for event in users["cfOnline"]:
            user_data = candidate["users"].get(event["handle"])
            if user_data is None:
                continue
            monitor = user_data["monitor"]
            submission_id = int(event["submissionId"])
            current_id = int(monitor.get("last_notified_submission_id", 0) or 0)
            if submission_id != current_id:
                monitor["last_notified_submission_id"] = submission_id
                monitor["last_submission_notice_at_seconds"] = now
                dirty = True

        if dirty:
            _commit_store(candidate)


async def claimNotification(group_id, kind, event):
    """Persist an at-most-once send reservation before touching the network.

    A send timeout can mean that a message was delivered. Reservations are
    therefore retained on every failure, including cancellation and restart.
    Only watermarks per user/group are kept, rather than an unbounded event log.
    """
    if kind not in ("cfOnline", "ratingChange"):
        raise ValueError("未知通知类型：{}".format(kind))
    now = int(time.time())
    async with _store_lock:
        candidate = copy.deepcopy(_store)
        user = candidate["users"].get(event["handle"])
        if user is None:
            return False
        receipts = user["monitor"].setdefault("delivery_attempts", {})
        receipt = receipts.setdefault(str(group_id), {})
        if kind == "cfOnline":
            submission_id = int(event["submissionId"])
            if submission_id == int(receipt.get("submission_id", 0)):
                return False
            previous_at = int(receipt.get("submission_attempt_at_seconds", 0))
            receipt["submission_id"] = submission_id
            created_at = event.get("creationTimeSeconds")
            if previous_at and (
                now - previous_at < 7200 or
                (created_at is not None and int(created_at) < previous_at + 7200)
            ):
                # Consume new submissions in this group's cooldown even if a
                # previous send or its confirmation failed.
                _commit_store(candidate)
                return False
            receipt["submission_attempt_at_seconds"] = now
        else:
            rating_pair = (int(event["ratingUpdateTimeSeconds"]), int(event["contestId"]))
            previous_pair = (
                int(receipt.get("rating_update_time_seconds", -1)),
                int(receipt.get("rating_contest_id", -1)),
            )
            if rating_pair <= previous_pair:
                return False
            receipt["rating_update_time_seconds"], receipt["rating_contest_id"] = rating_pair
        # If persistence fails, the exception prevents the caller from sending.
        _commit_store(candidate)
        return True


def formatSubmissionNotice(event):
    text = "检测到 cf用户 {} ({}) 有新提交，提交 ID：{}".format(
        event["handle"], event["remarks"], event["submissionId"]
    )
    if event.get("contestId") is not None:
        text += "，比赛 ID：{}".format(event["contestId"])
    if event.get("creationTimeSeconds") is not None:
        text += "，提交时间：{}".format(time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(event["creationTimeSeconds"])
        ))
    return text + "。\n"


async def returnBindList():
    async with _store_lock:
        users = copy.deepcopy(_store["users"])
    if not users:
        return "当前无监视选手"

    msg = "当前已监视选手如下:\n"
    for handle in sorted(users):
        remarks = users[handle]["monitor"].get("remarks", handle)
        msg += "{}({}) \n".format(handle, remarks)
    return msg


async def queryUser(id: str):
    url = cf_user_info_baseurl + id
    msg = MessageSegment.text("查询失败！请检查该用户是否存在")
    try:
        data = await requestCodeforces(url)
    except Exception as error:
        logger.warning(error)
        return msg

    if data.get("status") == "OK":
        for result in data.get("result", []):
            avatar_url = result.get("avatar")
            name = result.get("handle", id)
            rank = result.get("rank", "Unrated")
            contest_rating = result.get("rating", "0")
            max_rating = result.get("maxRating", "0")
            contribution = result.get("contribution", "0")
            friend_of = result.get("friendOfCount", "0")

            if avatar_url:
                async with AsyncClient() as client:
                    image_response = await client.get(avatar_url, timeout=10.0)
                msg = MessageSegment.image(image_response.content)
            else:
                msg = MessageSegment.text("")
            msg += Message(
                "\nname: " + str(name) +
                "\nrank: " + str(rank) +
                "\nrating: " + str(contest_rating) +
                "\nmax rating: " + str(max_rating) +
                "\ncontribution: " + str(contribution) +
                "\nfriend of: " + str(friend_of) + " users"
            )
            return msg
    else:
        logger.warning("查询 Codeforces 用户失败")
    return msg


async def returnRanklist():
    async with _store_lock:
        users = copy.deepcopy(_store["users"])
    rows = []
    for handle, user_data in users.items():
        rating = user_data["profile"].get("rating")
        rows.append((handle, rating if rating is not None else 0))
    return sorted(rows, key=lambda row: (-row[1], row[0]))


async def modifyRemarks(cf_id: str, cf_remarks: str):
    handle = cf_id.lower()
    async with _store_lock:
        if handle not in _store["users"]:
            return False
        candidate = copy.deepcopy(_store)
        candidate["users"][handle]["monitor"]["remarks"] = cf_remarks
        _commit_store(candidate)
    return True
