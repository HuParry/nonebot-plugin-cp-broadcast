"""Submission monitoring regression tests; no network or running bot required."""

import asyncio
import importlib.util
import json
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch


ROOT = Path(__file__).resolve().parents[1]


def load_store(data_dir):
    package_name = "_cp_broadcast_monitor_test"
    package = types.ModuleType(package_name)
    package.__path__ = [str(ROOT / "nonebot_plugin_cp_broadcast")]
    config = types.ModuleType(package_name + ".config")
    config.cp_broadcast_path = data_dir
    config.cf_user_info_baseurl = "https://example.invalid/info?handles="
    config.cf_user_status_baseurl = "https://example.invalid/status?handle={handle}"
    config.cf_user_rating_baseurl = "https://example.invalid/rating?handle={handle}"
    nonebot = types.ModuleType("nonebot")
    nonebot.get_driver = lambda: types.SimpleNamespace(
        on_startup=lambda fn: fn, on_shutdown=lambda fn: fn
    )
    adapter = types.ModuleType("nonebot.adapters.onebot.v11")
    adapter.Message = adapter.MessageSegment = object
    log = types.ModuleType("nonebot.log")
    log.logger = Mock()
    httpx = types.ModuleType("httpx")
    httpx.AsyncClient = MagicMock()
    spec = importlib.util.spec_from_file_location(
        package_name + ".json_store",
        ROOT / "nonebot_plugin_cp_broadcast/json_store.py",
    )
    module = importlib.util.module_from_spec(spec)
    modules = {
        package_name: package,
        package_name + ".config": config,
        "nonebot": nonebot,
        "nonebot.adapters": types.ModuleType("nonebot.adapters"),
        "nonebot.adapters.onebot": types.ModuleType("nonebot.adapters.onebot"),
        "nonebot.adapters.onebot.v11": adapter,
        "nonebot.log": log,
        "httpx": httpx,
        spec.name: module,
    }
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
        broadcast_spec = importlib.util.spec_from_file_location(
            package_name + ".broadcast",
            ROOT / "nonebot_plugin_cp_broadcast/broadcast.py",
        )
        broadcast = importlib.util.module_from_spec(broadcast_spec)
        broadcast_spec.loader.exec_module(broadcast)
        module.broadcast = broadcast
    return module


class SubmissionMonitorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = load_store(Path(self.directory.name))
        self.addCleanup(self.store._release_data_directory_lock)
        self.now = 20000
        self.store.time = types.SimpleNamespace(
            time=lambda: self.now, monotonic=time.monotonic,
            strftime=time.strftime, localtime=time.localtime
        )
        self.store.asyncio = types.SimpleNamespace(Lock=asyncio.Lock, sleep=AsyncMock())
        self.http_status = self.store.CF_UserStatus.getByHttp
        self.status_api = AsyncMock()
        self.store.CF_UserStatus.getByHttp = staticmethod(self.status_api)
        self.store.CF_UserInfo.getByHttp = staticmethod(AsyncMock(
            return_value=self.store.CF_UserInfo("sample", rating=1600)
        ))
        self.store.CF_UserRating.getAllByHttp = staticmethod(AsyncMock(return_value=[]))
        await self.store._on_startup()

    def status(self, submission_id, created=None):
        return self.store.CF_UserStatus(
            "sample", submission_id, 2000,
            self.now if created is None else created,
        )

    async def register(self, status):
        self.status_api.return_value = status
        self.assertTrue(await self.store.addUser("sample"))

    async def poll(self, status):
        self.status_api.return_value = status
        return await self.store.returnChangeInfo()

    def monitor(self):
        return self.store._store["users"]["sample"]["monitor"]

    async def test_registration_baseline_new_submission_and_delivery(self):
        await self.register(self.status(100))
        self.assertEqual((await self.poll(self.status(100)))["cfOnline"], [])
        changes = await self.poll(self.status(101))
        self.assertEqual(changes["cfOnline"][0]["submissionId"], 101)
        self.assertEqual(self.monitor()["last_processed_submission_id"], 101)
        await self.store.ackChangeInfo(changes)
        self.assertEqual((await self.poll(self.status(101)))["cfOnline"], [])
        saved = json.loads(self.store.JSON_PATH.read_text(encoding="utf-8"))
        self.assertEqual(saved["users"]["sample"]["monitor"]["last_notified_submission_id"], 101)

    async def test_failed_registration_request_does_not_announce_history(self):
        await self.register(None)
        self.assertIsNone(self.monitor()["last_processed_submission_id"])
        self.assertEqual((await self.poll(None))["cfOnline"], [])
        self.assertEqual((await self.poll(self.status(100, 1000)))["cfOnline"], [])
        self.assertEqual(len((await self.poll(self.status(101)))["cfOnline"]), 1)

    async def test_empty_history_allows_first_submission(self):
        await self.register(self.status(0))
        self.assertEqual(len((await self.poll(self.status(1)))["cfOnline"]), 1)

    async def test_cooldown_activity_is_not_replayed_after_restart(self):
        await self.register(self.status(100))
        await self.store.ackChangeInfo(await self.poll(self.status(101)))
        self.now += 60
        self.assertEqual((await self.poll(self.status(102)))["cfOnline"], [])
        self.assertEqual(self.monitor()["last_notified_submission_id"], 101)
        await self.store._on_startup()
        self.now += 7200
        self.assertEqual((await self.poll(self.status(102, 20060)))["cfOnline"], [])
        self.assertEqual(len((await self.poll(self.status(103)))["cfOnline"]), 1)

    async def test_delayed_cooldown_submission_is_skipped(self):
        await self.register(self.status(100))
        await self.store.ackChangeInfo(await self.poll(self.status(101)))
        self.now += 7200
        self.assertEqual((await self.poll(self.status(102, 20060)))["cfOnline"], [])
        self.assertEqual(len((await self.poll(self.status(103)))["cfOnline"]), 1)

    async def test_empty_failed_and_identical_results_do_not_change_saved_id(self):
        await self.register(self.status(100))
        for status in (self.status(0), None, self.status(100)):
            self.assertEqual((await self.poll(status))["cfOnline"], [])
        self.assertEqual(self.monitor()["last_processed_submission_id"], 100)
        self.assertEqual(len((await self.poll(self.status(101)))["cfOnline"]), 1)

    async def test_different_smaller_submission_id_is_detected_saved_and_sent(self):
        await self.register(self.status(100))
        self.monitor()["last_notified_submission_id"] = 100
        self.monitor()["delivery_attempts"] = {"good": {
            "submission_id": 100, "submission_attempt_at_seconds": self.now - 7200,
        }}
        changes = await self.poll(self.status(99))
        self.assertEqual(changes["cfOnline"][0]["submissionId"], 99)
        self.assertEqual(self.monitor()["last_processed_submission_id"], 99)
        self.store.broadcast.returnChangeInfo = AsyncMock(return_value=changes)
        self.store.broadcast.asyncio = types.SimpleNamespace(sleep=AsyncMock())
        send = AsyncMock()
        await self.store.broadcast.broadcastChanges(["good"], send)
        send.assert_awaited_once()
        self.assertEqual(self.monitor()["last_notified_submission_id"], 99)
        self.assertEqual((await self.poll(self.status(99)))["cfOnline"], [])

    async def test_sample_submission_id_295818395_is_one_event_despite_verdict_changes(self):
        await self.register(self.status(295818394))
        client = MagicMock()
        client.__aenter__.return_value = client
        self.store.AsyncClient = MagicMock(return_value=client)
        events = []
        for index in range(22):
            payload = {"status": "OK", "result": [{
                "id": 295818395, "contestId": 105471,
                "creationTimeSeconds": 1733796908,
                "problem": {"contestId": 105471, "index": "N", "name": "Python Program"},
                "verdict": "TESTING" if index == 0 else "OK",
                "passedTestCount": 0 if index == 0 else 5,
            }]}
            client.get = AsyncMock(return_value=Mock(text=json.dumps(payload)))
            status = await self.http_status("sample")
            events.extend((await self.poll(status))["cfOnline"])
            self.now += 600
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["submissionId"], 295818395)
        self.assertEqual(self.monitor()["last_processed_submission_id"], 295818395)

    async def test_detection_is_consumed_before_delivery_and_survives_reload(self):
        await self.register(self.status(100))
        changes = await self.poll(self.status(101))
        await self.store._on_startup()
        self.assertEqual((await self.poll(self.status(101)))["cfOnline"], [])
        await self.store.ackChangeInfo(changes)
        first_notice = self.monitor()["last_submission_notice_at_seconds"]
        self.now += 60
        await self.store.ackChangeInfo(changes)
        self.assertEqual(self.monitor()["last_submission_notice_at_seconds"], first_notice)

    async def test_detector_returns_same_submission_only_once_in_22_polls_without_ack(self):
        await self.register(self.status(100))
        generated = []
        for index in range(22):
            generated.extend((await self.poll(self.status(101, 20000)))["cfOnline"])
            self.now += 600
            if index == 10:
                await self.store._on_startup()
        self.assertEqual(len(generated), 1)
        self.assertEqual(generated[0]["submissionId"], 101)
        self.assertEqual(self.monitor()["last_processed_submission_id"], 101)
        self.assertEqual(self.monitor()["last_notified_submission_id"], 0)

    async def test_detector_cooldown_does_not_depend_on_sending_or_acknowledgement(self):
        await self.register(self.status(100))
        generated = []
        for index in range(22):
            generated.extend((await self.poll(self.status(101 + index)))["cfOnline"])
            self.now += 60
        self.assertEqual(len(generated), 1)
        self.assertEqual(self.monitor()["last_processed_submission_id"], 122)
        self.assertEqual(self.monitor()["last_notified_submission_id"], 0)

    async def test_detector_does_not_return_an_event_if_cursor_cannot_be_persisted(self):
        await self.register(self.status(100))
        with patch.object(self.store, "_atomic_write_json", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                await self.poll(self.status(101))
        self.assertEqual(self.monitor()["last_processed_submission_id"], 100)
        self.assertEqual(len((await self.poll(self.status(101)))["cfOnline"]), 1)
        self.assertEqual((await self.poll(self.status(101)))["cfOnline"], [])

    async def test_concurrent_detector_calls_generate_one_event_for_one_submission(self):
        await self.register(self.status(100))
        self.status_api.return_value = self.status(101)
        changes = await asyncio.gather(*(
            self.store.returnChangeInfo() for _ in range(22)
        ))
        self.assertEqual(sum(len(change["cfOnline"]) for change in changes), 1)

    async def test_submission_api_distinguishes_empty_failure_and_malformed_data(self):
        client = MagicMock()
        client.__aenter__.return_value = client
        self.store.AsyncClient = MagicMock(return_value=client)
        responses = [
            ({"status": "OK", "result": []}, 0),
            ({"status": "FAILED", "comment": "Unavailable"}, None),
            ({"status": "OK", "result": {}}, None),
            ({"status": "OK", "result": [{}]}, None),
            ({"status": "OK", "result": [{"id": 5, "creationTimeSeconds": 20000}]}, 5),
        ]
        for payload, expected in responses:
            response = Mock(text=json.dumps(payload))
            client.get = AsyncMock(return_value=response)
            result = await self.http_status("sample")
            if expected is None:
                self.assertIsNone(result)
            else:
                self.assertEqual(result.id, expected)
        client.get = AsyncMock(side_effect=TimeoutError("timeout"))
        self.assertIsNone(await self.http_status("sample"))

    async def prepare_broadcast(self, two_users=True):
        names = ("primal_potato", "7_divided_by_3") if two_users else ("sample",)
        self.store.CF_UserInfo.getByHttp = staticmethod(AsyncMock(
            side_effect=lambda handle: self.store.CF_UserInfo(handle, rating=1600)
        ))
        changes = {"ratingChange": [], "cfOnline": []}
        for index, name in enumerate(names):
            self.status_api.return_value = self.store.CF_UserStatus(name, 0)
            await self.store.addUser(name)
            changes["cfOnline"].append({
                "handle": name, "remarks": name, "submissionId": 101 + index,
                "contestId": 2271 if index == 0 else 106761,
                "creationTimeSeconds": self.now,
            })
        broadcast = self.store.broadcast
        broadcast.returnChangeInfo = AsyncMock(return_value=changes)
        broadcast.asyncio = types.SimpleNamespace(sleep=AsyncMock())
        return changes

    async def test_22_cycles_partial_group_failure_never_resends_the_two_messages(self):
        await self.prepare_broadcast()
        calls = []
        async def send(group_id, message):
            calls.append((group_id, message))
            if group_id == "failed":
                raise TimeoutError("delivery result unknown")
        for _ in range(22):
            await self.store.broadcast.broadcastChanges(["good", "failed"], send)
            self.now += 600
        self.assertEqual(len([call for call in calls if call[0] == "good"]), 2)
        self.assertEqual(len([call for call in calls if call[0] == "failed"]), 2)
        self.assertIn("提交 ID：101", calls[0][1])
        self.assertNotIn("又开始", calls[0][1])

    async def test_22_cycles_confirmation_disk_failure_does_not_repeat_sends(self):
        await self.prepare_broadcast()
        original_write = self.store._atomic_write_json
        def fail_confirmation(data):
            if any(user["monitor"].get("last_notified_submission_id", 0)
                   for user in data["users"].values()):
                raise OSError("confirmation write failed")
            original_write(data)
        send = AsyncMock()
        with patch.object(self.store, "_atomic_write_json", side_effect=fail_confirmation):
            for _ in range(22):
                await self.store.broadcast.broadcastChanges(["good"], send)
                self.now += 600
        self.assertEqual(send.await_count, 2)
        await self.store._on_startup()
        await self.store.broadcast.broadcastChanges(["good"], send)
        self.assertEqual(send.await_count, 2)

    async def test_real_polling_22_times_with_failed_confirmation_sends_each_user_once(self):
        await self.prepare_broadcast()
        self.store.broadcast.returnChangeInfo = self.store.returnChangeInfo
        self.store.broadcast.ackChangeInfo = AsyncMock(side_effect=OSError("write failed"))
        self.status_api.side_effect = lambda handle: self.store.CF_UserStatus(
            handle, 101 if handle == "primal_potato" else 102,
            2271 if handle == "primal_potato" else 106761, 20000,
        )
        send = AsyncMock()
        for _ in range(22):
            await self.store.broadcast.broadcastChanges(["good"], send)
            self.now += 600
        self.assertEqual(send.await_count, 2)
        sent = [call.kwargs["message"] for call in send.await_args_list]
        self.assertEqual(sum("primal_potato" in message for message in sent), 1)
        self.assertEqual(sum("7_divided_by_3" in message for message in sent), 1)

    async def test_changing_submission_ids_in_one_contest_cannot_bypass_group_cooldown(self):
        changes = await self.prepare_broadcast(two_users=False)
        self.store.broadcast.ackChangeInfo = AsyncMock(side_effect=OSError("write failed"))
        send = AsyncMock()
        for index in range(22):
            changes["cfOnline"][0].update(
                submissionId=101 + index, creationTimeSeconds=self.now
            )
            await self.store.broadcast.broadcastChanges(["good"], send)
            self.now += 60
        send.assert_awaited_once()

    async def test_disk_failure_before_reservation_prevents_every_send(self):
        await self.prepare_broadcast()
        send = AsyncMock()
        with patch.object(self.store, "_atomic_write_json", side_effect=OSError("disk full")):
            for _ in range(22):
                await self.store.broadcast.broadcastChanges(["good"], send)
        send.assert_not_awaited()
        await self.store.broadcast.broadcastChanges(["good"], send)
        self.assertEqual(send.await_count, 2)

    async def test_22_concurrent_broadcasts_reserve_each_message_once(self):
        await self.prepare_broadcast()
        send = AsyncMock(side_effect=lambda **kwargs: None)
        await asyncio.gather(*(
            self.store.broadcast.broadcastChanges(["good"], send) for _ in range(22)
        ))
        self.assertEqual(send.await_count, 2)

    async def test_restart_after_cancellation_does_not_replay_a_reserved_message(self):
        await self.prepare_broadcast(two_users=False)
        send = AsyncMock(side_effect=asyncio.CancelledError())
        with self.assertRaises(asyncio.CancelledError):
            await self.store.broadcast.broadcastChanges(["good"], send)
        self.store._release_data_directory_lock()
        await self.store._on_startup()
        self.now += 10800
        send.side_effect = None
        await self.store.broadcast.broadcastChanges(["good"], send)
        send.assert_awaited_once()

    async def test_duplicate_group_configuration_and_repeated_poll_are_deduplicated(self):
        await self.prepare_broadcast()
        send = AsyncMock()
        for _ in range(22):
            await self.store.broadcast.broadcastChanges([1, "1", " 1 ", "2"], send)
        self.assertEqual(send.await_count, 4)

    async def test_group_cooldown_survives_failed_send_and_suppresses_new_ids(self):
        changes = await self.prepare_broadcast(two_users=False)
        send = AsyncMock(side_effect=TimeoutError("may already be delivered"))
        await self.store.broadcast.broadcastChanges(["good"], send)
        self.now += 60
        changes["cfOnline"][0].update(submissionId=102, creationTimeSeconds=self.now)
        await self.store.broadcast.broadcastChanges(["good"], send)
        self.assertEqual(send.await_count, 1)
        self.now += 7200
        await self.store.broadcast.broadcastChanges(["good"], send)
        self.assertEqual(send.await_count, 1)
        changes["cfOnline"][0].update(submissionId=103, creationTimeSeconds=self.now)
        await self.store.broadcast.broadcastChanges(["good"], send)
        self.assertEqual(send.await_count, 2)

    async def test_rating_notifications_also_have_durable_per_group_deduplication(self):
        changes = await self.prepare_broadcast(two_users=False)
        changes["cfOnline"] = []
        changes["ratingChange"] = [{
            "handle": "sample", "remarks": "sample", "contestId": contest_id,
            "ratingUpdateTimeSeconds": 20000 + contest_id,
            "oldRating": 1500, "newRating": 1600,
        } for contest_id in (2, 1)]
        self.store.broadcast.ackChangeInfo = AsyncMock(side_effect=OSError("disk failure"))
        send = AsyncMock()
        for _ in range(22):
            await self.store.broadcast.broadcastChanges(["good"], send)
        self.assertEqual(send.await_count, 2)

    async def test_no_destinations_skips_api_polling(self):
        await self.prepare_broadcast()
        await self.store.broadcast.broadcastChanges([], AsyncMock())
        self.store.broadcast.returnChangeInfo.assert_not_awaited()

    async def test_second_writer_is_refused_and_lock_is_released_on_shutdown(self):
        await self.register(self.status(100))
        other = load_store(Path(self.directory.name))
        self.addCleanup(other._release_data_directory_lock)
        with self.assertRaisesRegex(RuntimeError, "其他进程占用"):
            await other._on_startup()
        await self.store._on_shutdown()
        await other._on_startup()
        self.assertIn("sample", other._store["users"])

    async def test_concurrent_api_requests_obey_rate_limit_even_after_failure(self):
        api_clock = [0.0]
        starts = []
        self.store.time.monotonic = lambda: api_clock[0]
        async def sleep(delay):
            api_clock[0] += delay
            await asyncio.sleep(0)
        self.store.asyncio.sleep = sleep
        client = MagicMock()
        client.__aenter__.return_value = client
        async def get(url, timeout):
            starts.append(api_clock[0])
            if url == "failed":
                raise TimeoutError("timeout")
            return Mock(text=json.dumps({"status": "OK", "result": []}))
        client.get = get
        self.store.AsyncClient = MagicMock(return_value=client)
        results = await asyncio.gather(
            self.store.requestCodeforces("failed"),
            self.store.requestCodeforces("second"),
            self.store.requestCodeforces("third"),
            return_exceptions=True,
        )
        self.assertIsInstance(results[0], TimeoutError)
        self.assertEqual(len(starts), 3)
        self.assertTrue(all(b - a >= 2 for a, b in zip(starts, starts[1:])))


if __name__ == "__main__":
    unittest.main()
