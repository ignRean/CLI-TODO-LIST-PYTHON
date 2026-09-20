import sys
import os
import json
import unittest
import types

# Ensure repo root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

class MockStorage:
    def __init__(self):
        self.store = {}
    def getItem(self, k):
        return self.store.get(k)
    def setItem(self, k, v):
        self.store[k] = str(v)
    def removeItem(self, k):
        self.store.pop(k, None)

class MockPyTodoBridge:
    def __init__(self):
        self.step_sec = 300
        self.last_payload = None
        self.dashboard_mode = False

    def getFocusStep(self):
        return self.step_sec

    def setFocusStep(self, sec):
        self.step_sec = int(sec)

    def enterFocusMode(self, payload_str):
        self.last_payload = json.loads(payload_str)

    def triggerBackgroundSync(self):
        pass

    def playSound(self, name):
        pass

    def getTerminalCols(self):
        return 100

    def getLocalISODate(self):
        return "2026-09-19"

    def getTheme(self):
        return getattr(self, "theme", "classic")

    def setTheme(self, name):
        self.theme = str(name)
        return self.theme

    def getRetentionDays(self):
        return getattr(self, "retention_days", 3)

    def setRetentionDays(self, days):
        self.retention_days = int(days)
        return True

    def isSoundEnabled(self):
        return getattr(self, "sound", True)

    def setSoundEnabled(self, val):
        self.sound = bool(val)

class MockWindow:
    def __init__(self):
        self.PyTodoBridge = MockPyTodoBridge()
        self.localStorage = MockStorage()
        self.term = type("Term", (), {"cols": 100})()
        self.Date = type("Date", (), {
            "now": lambda: 1700000000000,
            "new": lambda: type("DateObj", (), {"getTimezoneOffset": lambda: 0})()
        })()

mock_win = MockWindow()
js_mock = types.ModuleType("js")
js_mock.window = mock_win
js_mock.supabaseClient = None
sys.modules["js"] = js_mock

from main import (
    parse_duration_seconds,
    parse_duration,
    cli_focus,
    cli_config,
    handle_focus_step_command,
    get_autocomplete_suggestions,
    get_local_todos,
    save_local_todos
)

class TestFocusImprovements(unittest.TestCase):
    def setUp(self):
        sys.modules["js"].window = mock_win
        import main
        main.window = mock_win
        self.bridge = mock_win.PyTodoBridge
        self.bridge.step_sec = 300
        self.bridge.last_payload = None
        mock_win.localStorage.store.clear()

        # Set up test todos
        self.test_todos = [
            {
                "id": "1",
                "uuid": "test-uuid-1",
                "title": "Deploy Cluster",
                "task_date": "2026-09-19",
                "done": False,
                "duration_minutes": 25,
                "due_time": "18:00",
                "subtasks": [
                    {"id": "1.1", "title": "Check nodes", "done": False},
                    {"id": "1.2", "title": "Run smoke tests", "done": True}
                ],
                "created_at": "2026-09-19T08:00:00Z",
                "updated_at": "2026-09-19T08:00:00Z",
                "synced": True
            },
            {
                "id": "2",
                "uuid": "test-uuid-2",
                "title": "Write Specs",
                "task_date": "2026-09-19",
                "done": False,
                "duration_minutes": 15,
                "due_time": None,
                "subtasks": [],
                "created_at": "2026-09-19T09:00:00Z",
                "updated_at": "2026-09-19T09:00:00Z",
                "synced": True
            }
        ]
        save_local_todos(self.test_todos)

    def test_parse_duration_seconds(self):
        self.assertEqual(parse_duration_seconds("42m"), 42 * 60)
        self.assertEqual(parse_duration_seconds("25m"), 25 * 60)
        self.assertEqual(parse_duration_seconds("1h"), 3600)
        self.assertEqual(parse_duration_seconds("1.5h"), 5400)
        self.assertEqual(parse_duration_seconds("90s"), 90)
        self.assertEqual(parse_duration_seconds("1h 30m"), 5400)
        self.assertEqual(parse_duration_seconds("45"), 45 * 60)
        self.assertIsNone(parse_duration_seconds("invalid"))
        self.assertIsNone(parse_duration_seconds("-5m"))

    def test_parse_duration_minutes(self):
        self.assertEqual(parse_duration("42m"), 42)
        self.assertEqual(parse_duration("1.5h"), 90)
        self.assertEqual(parse_duration("60s"), 1)
        self.assertEqual(parse_duration("30s"), 1) # min 1 min

    def test_focus_flag_parsing(self):
        # focus 1 -time 42m
        res = cli_focus(["1", "-time", "42m"])
        self.assertEqual(res, "")
        self.assertIsNotNone(self.bridge.last_payload)
        self.assertEqual(self.bridge.last_payload["id"], "1")
        self.assertEqual(self.bridge.last_payload["duration_sec"], 42 * 60)
        self.assertFalse(self.bridge.last_payload["is_fullscreen"])

        # focus 1 --time 15m -full
        res = cli_focus(["1", "--time", "15m", "-full"])
        self.assertEqual(res, "")
        self.assertEqual(self.bridge.last_payload["duration_sec"], 15 * 60)
        self.assertTrue(self.bridge.last_payload["is_fullscreen"])

        # focus 1 -t 50m
        res = cli_focus(["1", "-t", "50m"])
        self.assertEqual(res, "")
        self.assertEqual(self.bridge.last_payload["duration_sec"], 50 * 60)

        # 24h ceiling boundary check
        res = cli_focus(["1", "-time", "25h"])
        self.assertIn("Maximum focus session duration is 24h", res)

    def test_focus_space_notation_with_flag(self):
        # focus 1 1 -time 42m -> subtask 1.1
        res = cli_focus(["1", "1", "-time", "42m"])
        self.assertEqual(res, "")
        self.assertEqual(self.bridge.last_payload["id"], "1.1")
        self.assertEqual(self.bridge.last_payload["title"], "Check nodes")
        self.assertEqual(self.bridge.last_payload["parent_title"], "Deploy Cluster")
        self.assertEqual(self.bridge.last_payload["duration_sec"], 42 * 60)

    def test_focus_positional_durations(self):
        # focus 1 25m
        res = cli_focus(["1", "25m"])
        self.assertEqual(res, "")
        self.assertEqual(self.bridge.last_payload["id"], "1")
        self.assertEqual(self.bridge.last_payload["duration_sec"], 25 * 60)

        # focus 1 1 10m
        res = cli_focus(["1", "1", "10m"])
        self.assertEqual(res, "")
        self.assertEqual(self.bridge.last_payload["id"], "1.1")
        self.assertEqual(self.bridge.last_payload["duration_sec"], 10 * 60)

    def test_focus_step_and_config(self):
        # focus step
        res = cli_focus(["step"])
        self.assertIn("Current focus timer step:", res)

        # focus step 10m
        res = cli_focus(["step", "10m"])
        self.assertIn("Focus timer adjustment step set to:", res)
        self.assertEqual(self.bridge.step_sec, 600)

        # config focus.step 15m
        res = cli_config(["focus.step", "15m"])
        self.assertIn("Focus timer adjustment step set to:", res)
        self.assertEqual(self.bridge.step_sec, 900)

        # config display
        res = cli_config([])
        self.assertIn("focus.step", res)
        self.assertIn("15m", res)

    def test_autocompletion(self):
        # Autocomplete verbs includes config
        verbs = json.loads(get_autocomplete_suggestions(""))
        self.assertIn("config", verbs)
        self.assertIn("focus", verbs)

        # Autocomplete focus options
        focus_opts = json.loads(get_autocomplete_suggestions("focus "))
        self.assertIn("step", focus_opts)
        self.assertIn("1", focus_opts)
        self.assertIn("1.1", focus_opts)

        # Autocomplete config keys
        cfg_opts = json.loads(get_autocomplete_suggestions("config "))
        self.assertIn("focus.step", cfg_opts)

if __name__ == "__main__":
    unittest.main()
