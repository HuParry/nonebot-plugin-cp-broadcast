"""Query output and command handling checks without a live QQ connection."""

import ast
from io import BytesIO
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock

from PIL import Image

from test_submission_monitor import ROOT, load_store


class FakeActionFailed(Exception):
    pass


class UserQueryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = load_store(Path(directory.name))
        self.store.MessageSegment = types.SimpleNamespace(
            text=lambda value: [("text", value)],
            image=lambda value: [("image", value)],
        )
        self.store.requestCodeforces = AsyncMock(return_value={"status": "OK", "result": [{
            "handle": "HuParry", "rating": 1600, "rank": "expert",
            "lastOnlineTimeSeconds": 1672531200,
            "avatar": "https://userpic.codeforces.org/2294805/avatar/39c98e2c0afb123c.jpg",
        }]})
        self.client = MagicMock()
        self.client.__aenter__.return_value = self.client
        buffer = BytesIO()
        Image.new("RGB", (80, 80), (220, 40, 100)).save(buffer, format="PNG")
        self.avatar_bytes = buffer.getvalue()
        self.client.get = AsyncMock(return_value=Mock(
            content=self.avatar_bytes, headers={"content-type": "image/png"},
        ))
        self.store.AsyncClient = MagicMock(return_value=self.client)

    async def test_default_query_embeds_rewritten_avatar_in_one_valid_png(self):
        message = await self.store.queryUser(" HuParry ")
        self.assertEqual([kind for kind, value in message], ["image"])
        with Image.open(BytesIO(message[0][1])) as image:
            image.load()
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.mode, "RGB")
            self.assertEqual(image.size, (960, 340))
            self.assertEqual(image.n_frames, 1)
            self.assertEqual(image.getpixel((80, 120)), (220, 40, 100))
        self.assertLess(len(message[0][1]), 200000)
        self.assertEqual(self.client.get.await_args.args[0],
                         "https://codeforces.com/userpic.codeforces.org/2294805/avatar/39c98e2c0afb123c.jpg")
        self.store.requestCodeforces.assert_awaited_once_with(
            "https://example.invalid/info?handles=HuParry"
        )

    def test_avatar_url_rewrite_preserves_avatar_path_and_filename(self):
        original = "https://userpic.codeforces.org/2294805/avatar/39c98e2c0afb123c.jpg"
        expected = "https://codeforces.com/userpic.codeforces.org/2294805/avatar/39c98e2c0afb123c.jpg"
        self.assertEqual(self.store._normalize_avatar_url(original), expected)
        self.assertEqual(self.store._normalize_avatar_url(original.replace("https:", "")), expected)
        self.assertEqual(self.store._normalize_avatar_url(expected), expected)
        self.assertIsNone(self.store._normalize_avatar_url("https://example.invalid/photo.jpg"))

    async def test_missing_avatar_uses_default_no_title_image(self):
        self.store.requestCodeforces.return_value["result"][0].pop("avatar")
        await self.store.queryUser("HuParry")
        self.client.get.assert_awaited_once_with(
            "https://codeforces.com/userpic.codeforces.org/no-title.jpg",
            timeout=10.0, follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://codeforces.com/"},
        )

    async def test_failed_avatar_download_tries_default_once(self):
        response = self.client.get.return_value
        self.client.get.side_effect = [TimeoutError("avatar timeout"), response]
        message = await self.store.queryUser("HuParry")
        self.assertEqual(message[0][0], "image")
        self.assertEqual(self.client.get.await_count, 2)
        self.assertTrue(self.client.get.await_args.args[0].endswith("/no-title.jpg"))

    async def test_all_avatar_downloads_fail_but_card_still_renders(self):
        self.client.get.side_effect = TimeoutError("download timeout")
        message = await self.store.queryUser("HuParry")
        self.assertEqual(message[0][0], "image")
        self.assertEqual(self.client.get.await_count, 2)
        with Image.open(BytesIO(message[0][1])) as image:
            self.assertEqual(image.size, (960, 340))

    def test_corrupt_avatar_bytes_do_not_break_rendering(self):
        png = self.store.render_user_card({"handle": "HuParry"}, b"not an image")
        with Image.open(BytesIO(png)) as image:
            image.load()
            self.assertEqual(image.size, (960, 340))

    async def test_text_option_skips_rendering_and_avatar_download(self):
        self.store.render_user_card = Mock(side_effect=AssertionError("must not render"))
        message = await self.store.queryUser("HuParry", text_only=True)
        self.assertEqual(message[0][0], "text")
        self.assertIn("rating: 1600", message[0][1])
        self.assertIn("Last Online: 2023-01-01 08:00:00 (UTC+8)", message[0][1])
        self.assertNotIn("friend of", message[0][1].lower())
        self.store.render_user_card.assert_not_called()
        self.store.AsyncClient.assert_not_called()

    def test_last_online_uses_utc_plus_8_and_handles_unknown_times(self):
        self.assertEqual(self.store.format_last_online(0), "1970-01-01 08:00:00")
        self.assertEqual(self.store.format_last_online(1672531200), "2023-01-01 08:00:00")
        for value in (None, "invalid", 10 ** 100, float("inf")):
            self.assertEqual(self.store.format_last_online(value), "-")

    async def test_rendering_failure_keeps_user_information(self):
        self.store.render_user_card = Mock(side_effect=RuntimeError("render failed"))
        message = await self.store.queryUser("HuParry")
        self.assertEqual(message[0][0], "text")
        self.assertIn("rating: 1600", message[0][1])

    async def test_missing_pillow_falls_back_to_text(self):
        self.store.render_user_card = None
        message = await self.store.queryUser("HuParry")
        self.assertEqual(message[0][0], "text")
        self.assertIn("HuParry", message[0][1])

    def test_renderer_handles_unrated_and_long_names_without_network(self):
        for profile in (
            {"handle": "new_user"},
            {"handle": "x" * 100, "rating": 3200, "rank": "legendary grandmaster",
             "maxRating": 3500, "maxRank": "legendary grandmaster", "contribution": -20,
             "registrationTimeSeconds": "invalid"},
        ):
            with Image.open(BytesIO(self.store.render_user_card(profile))) as image:
                image.load()
                self.assertEqual(image.size, (960, 340))
        self.store.AsyncClient.assert_not_called()

    async def test_api_failure_is_distinguished_from_unknown_handle(self):
        self.store.requestCodeforces.side_effect = TimeoutError("API timeout")
        message = await self.store.queryUser("HuParry")
        self.assertIn("请求失败", message[0][1])
        self.assertNotIn("是否存在", message[0][1])
        self.store.AsyncClient.assert_not_called()

    def command(self):
        source = (ROOT / "nonebot_plugin_cp_broadcast/codeforces.py").read_text()
        node = next(node for node in ast.parse(source).body
                    if isinstance(node, ast.AsyncFunctionDef) and node.name == "query_handle")
        node.decorator_list = []
        query = types.SimpleNamespace(finish=AsyncMock())
        namespace = {
            "Bot": object, "GroupMessageEvent": object, "Message": object,
            "CommandArg": lambda: None, "query": query, "logger": Mock(),
            "ActionFailed": FakeActionFailed,
            "queryUser": AsyncMock(return_value="user info"),
        }
        exec(compile(ast.Module(body=[node], type_ignores=[]), "query_handle", "exec"), namespace)
        return namespace

    async def test_command_text_option_and_send_timeout_do_not_trigger_retry(self):
        namespace = self.command()
        namespace["query"].finish.side_effect = FakeActionFailed("send timeout")
        args = Mock(extract_plain_text=Mock(return_value=" HuParry --text "))
        await namespace["query_handle"](None, None, args)
        namespace["queryUser"].assert_awaited_once_with("HuParry", text_only=True)
        namespace["query"].finish.assert_awaited_once_with("user info")
        namespace["logger"].error.assert_called_once()

    async def test_normal_matcher_finish_control_flow_is_not_swallowed(self):
        class Finished(Exception):
            pass
        namespace = self.command()
        namespace["query"].finish.side_effect = Finished()
        args = Mock(extract_plain_text=Mock(return_value="HuParry"))
        with self.assertRaises(Finished):
            await namespace["query_handle"](None, None, args)
        namespace["queryUser"].assert_awaited_once_with("HuParry", text_only=False)
        namespace["logger"].error.assert_not_called()

    async def test_removed_avatar_option_is_rejected(self):
        namespace = self.command()
        args = Mock(extract_plain_text=Mock(return_value="HuParry --avatar"))
        await namespace["query_handle"](None, None, args)
        namespace["queryUser"].assert_not_awaited()
        namespace["query"].finish.assert_awaited_once()

    async def test_conflicting_options_do_not_query_or_send_user_information(self):
        namespace = self.command()
        args = Mock(extract_plain_text=Mock(return_value="HuParry --text --avatar"))
        await namespace["query_handle"](None, None, args)
        namespace["queryUser"].assert_not_awaited()
        namespace["query"].finish.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
