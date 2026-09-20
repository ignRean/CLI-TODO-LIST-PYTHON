import sys
import os
import unittest
import json
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 1. Mock 'js' module before importing main
mock_js = MagicMock()
mock_window = MagicMock()
mock_storage = {}

def mock_getItem(k):
    return mock_storage.get(k, None)

def mock_setItem(k, v):
    mock_storage[k] = str(v)

def mock_removeItem(k):
    if k in mock_storage:
        del mock_storage[k]

def mock_clear():
    mock_storage.clear()

mock_window.localStorage.getItem = mock_getItem
mock_window.localStorage.setItem = mock_setItem
mock_window.localStorage.removeItem = mock_removeItem
mock_window.localStorage.clear = mock_clear

# Mock Bridge
class MockBridge:
    def __init__(self):
        self.theme = "classic"
        self.retention = 3
        self.focus_step = 300
        self.sound = True
        self.is_dashboard = False
        self.is_focus = False
        self.iso_date = "2026-09-20"

    def getLocalISODate(self):
        return self.iso_date

    def getTerminalCols(self):
        return 80

    def getTheme(self):
        return self.theme

    def setTheme(self, name):
        valid = ["classic", "matrix", "cyberpunk", "dracula", "nord", "monokai", "solarized"]
        if name in valid:
            self.theme = name
            return name
        return "classic"

    def getRetentionDays(self):
        return self.retention

    def setRetentionDays(self, d):
        self.retention = int(d)
        return True

    def getFocusStep(self):
        return self.focus_step

    def setFocusStep(self, s):
        self.focus_step = int(s)
        return True

    def isSoundEnabled(self):
        return self.sound

    def setSoundEnabled(self, val):
        self.sound = bool(val)

    def playSound(self, sound_type):
        pass

    def triggerBackgroundSync(self):
        pass

bridge = MockBridge()
mock_window.PyTodoBridge = bridge
mock_js.window = mock_window
mock_js.supabaseClient = MagicMock()
sys.modules['js'] = mock_js

# Now import main
import main

class TestNewFeatures(unittest.TestCase):
    def setUp(self):
        main.window = mock_window
        sys.modules['js'].window = mock_window
        mock_storage.clear()
        bridge.iso_date = "2026-09-20"
        bridge.retention = 3
        bridge.theme = "classic"

    def test_theme_command(self):
        """Verify theme command lists and applies themes."""
        res = main.cli_theme([])
        self.assertIn("classic", res)
        self.assertIn("matrix", res)

        # Set theme to matrix
        res2 = main.cli_theme(["matrix"])
        self.assertIn("Theme switched to 'matrix'", res2)
        self.assertEqual(bridge.theme, "matrix")

        # Invalid theme
        res3 = main.cli_theme(["invalid_theme"])
        self.assertIn("Error: Unknown theme", res3)

    def test_config_retention(self):
        """Verify config retention sets and clamps retention window."""
        res = main.cli_config(["retention", "5"])
        self.assertIn("Overdue retention window set to 5 days", res)
        self.assertEqual(main.get_retention_days(), 5)

        # Out of bounds
        res2 = main.cli_config(["retention", "9"])
        self.assertIn("Error: Retention window must be between 1 and 7 days", res2)

    def test_rollover_and_history_archival(self):
        """Verify uncompleted past tasks are archived to history on day rollover."""
        # Set date to Sept 18
        bridge.iso_date = "2026-09-18"
        todos = [
            {"id": "1", "uuid": "u1", "title": "Task 1 Done", "task_date": "2026-09-18", "done": True, "subtasks": []},
            {"id": "2", "uuid": "u2", "title": "Task 2 Incomplete", "task_date": "2026-09-18", "done": False, "subtasks": [
                {"id": "2.1", "title": "Sub 1", "done": False}
            ]}
        ]
        main.save_local_todos(todos)

        # Advance to Sept 19
        bridge.iso_date = "2026-09-19"
        wiped = main.enforce_day_rollover()
        self.assertEqual(wiped, 1)

        # History should contain Task 2 under Sept 18
        hist = main.get_history_todos()
        self.assertIn("2026-09-18", hist)
        self.assertEqual(len(hist["2026-09-18"]), 1)
        self.assertEqual(hist["2026-09-18"][0]["title"], "Task 2 Incomplete")

        # Active board should be empty for Sept 19
        active = main.get_local_todos()
        self.assertEqual(len(active), 0)

        # Streak should be 0 because Task 2 was incomplete
        st = main.get_streak_data()
        self.assertEqual(st["current_streak"], 0)

    def test_streak_increment_on_100_percent_day(self):
        """Verify streak increments when 100% of tasks completed before midnight."""
        # Day 1: Sept 18 (all completed)
        bridge.iso_date = "2026-09-18"
        todos = [
            {"id": "1", "uuid": "u1", "title": "Task A", "task_date": "2026-09-18", "done": True, "subtasks": []},
            {"id": "2", "uuid": "u2", "title": "Task B", "task_date": "2026-09-18", "done": True, "subtasks": []}
        ]
        main.save_local_todos(todos)

        # Advance to Sept 19
        bridge.iso_date = "2026-09-19"
        main.enforce_day_rollover()
        st = main.get_streak_data()
        self.assertEqual(st["current_streak"], 1)
        self.assertEqual(st["highest_streak"], 1)

        # Day 2: Sept 19 (all completed)
        todos_19 = [
            {"id": "1", "uuid": "u3", "title": "Task C", "task_date": "2026-09-19", "done": True, "subtasks": []}
        ]
        main.save_local_todos(todos_19)

        # Advance to Sept 20
        bridge.iso_date = "2026-09-20"
        main.enforce_day_rollover()
        st2 = main.get_streak_data()
        self.assertEqual(st2["current_streak"], 2)
        self.assertEqual(st2["highest_streak"], 2)

        # Day 3: Sept 20 (failed: 1 done, 1 incomplete)
        todos_20 = [
            {"id": "1", "uuid": "u4", "title": "Task D", "task_date": "2026-09-20", "done": True, "subtasks": []},
            {"id": "2", "uuid": "u5", "title": "Task E", "task_date": "2026-09-20", "done": False, "subtasks": []}
        ]
        main.save_local_todos(todos_20)

        # Advance to Sept 21
        bridge.iso_date = "2026-09-21"
        main.enforce_day_rollover()
        st3 = main.get_streak_data()
        self.assertEqual(st3["current_streak"], 0)
        self.assertEqual(st3["highest_streak"], 2)  # ATH preserved!

    def test_revive_by_day_number(self):
        """Verify revive <day> <id> resurrects task into today's active list with next integer ID."""
        bridge.iso_date = "2026-09-20"
        # Today has 1 active task
        active_today = [
            {"id": "1", "uuid": "active-1", "title": "Existing Today Task", "task_date": "2026-09-20", "done": False, "subtasks": []}
        ]
        main.save_local_todos(active_today)

        # History has an overdue task from Day 18 (2026-09-18)
        hist = {
            "2026-09-18": [
                {
                    "id": "1",
                    "uuid": "hist-uuid-1",
                    "title": "Quarterly Report",
                    "task_date": "2026-09-18",
                    "done": False,
                    "subtasks": [
                        {"id": "1.1", "title": "Gather stats", "done": False}
                    ]
                }
            ]
        }
        main.save_history_todos(hist)

        # Revive task #1 from Day 18 using 'revive 18 1'
        res = main.cli_revive(["18", "1"])
        self.assertIn("Resurrected task to today's active list", res)
        self.assertIn("#2", res)

        # Verify active board now has task #2
        active_after = main.get_local_todos()
        self.assertEqual(len(active_after), 2)
        revived = active_after[1]
        self.assertEqual(revived["id"], "2")
        self.assertEqual(revived["title"], "Quarterly Report")
        self.assertEqual(revived["task_date"], "2026-09-20")
        self.assertNotEqual(revived["uuid"], "hist-uuid-1")
        self.assertEqual(revived["subtasks"][0]["id"], "2.1")

        # History for Sept 18 should now be empty
        hist_after = main.get_history_todos()
        self.assertNotIn("2026-09-18", hist_after)

    def test_revive_by_history_tag(self):
        """Verify revive H1 resurrects task by unique history tag."""
        bridge.iso_date = "2026-09-20"
        hist = {
            "2026-09-19": [
                {"id": "5", "uuid": "h5", "title": "Fix memory leak", "task_date": "2026-09-19", "done": False, "subtasks": []}
            ]
        }
        main.save_history_todos(hist)

        res = main.cli_revive(["H1"])
        self.assertIn("Resurrected task to today's active list", res)
        active = main.get_local_todos()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["title"], "Fix memory leak")

    def test_revive_ambiguity_handling(self):
        """Verify revive <id> detects collisions across dates and prompts user to disambiguate."""
        bridge.iso_date = "2026-09-20"
        hist = {
            "2026-09-19": [
                {"id": "1", "uuid": "h19", "title": "Fix leak", "task_date": "2026-09-19", "done": False, "subtasks": []}
            ],
            "2026-09-18": [
                {"id": "1", "uuid": "h18", "title": "Buy milk", "task_date": "2026-09-18", "done": False, "subtasks": []}
            ]
        }
        main.save_history_todos(hist)

        res = main.cli_revive(["1"])
        self.assertIn("Ambiguous Task ID #1 found on multiple dates", res)
        self.assertIn("revive <day> 1", res)

    def test_history_display(self):
        """Verify cli_history renders date headers and tasks properly."""
        bridge.iso_date = "2026-09-20"
        hist = {
            "2026-09-19": [
                {"id": "1", "uuid": "h1", "title": "Write unit tests", "task_date": "2026-09-19", "done": False, "due_time": "18:00", "duration_minutes": 30, "subtasks": []}
            ]
        }
        main.save_history_todos(hist)
        output = main.cli_history([])
        self.assertIn("OVERDUE & HISTORY GRAVEYARD", output)
        self.assertIn("Yesterday (2026-09-19)", output)
        self.assertIn("[H1]", output)
        self.assertIn("Write unit tests", output)

    def test_streak_display(self):
        """Verify cli_streak output contains streak stats and intraday status."""
        bridge.iso_date = "2026-09-20"
        main.save_streak_data({
            "current_streak": 5,
            "highest_streak": 12,
            "last_evaluated_date": "2026-09-19",
            "history_log": {
                "2026-09-19": {"total": 4, "done": 4, "success": True}
            }
        })
        output = main.cli_streak([])
        self.assertIn("DISCIPLINE STREAK ENGINE", output)
        self.assertIn("5 Days", output)
        self.assertIn("12 Days", output)
        self.assertIn("2026-09-19", output)

    def test_autocomplete_suggestions(self):
        """Verify autocomplete suggests new verbs, config keys, and themes."""
        # Top-level verbs
        verbs_json = main.get_autocomplete_suggestions("h")
        verbs = json.loads(verbs_json)
        self.assertIn("history", verbs)

        verbs_json2 = main.get_autocomplete_suggestions("rev")
        self.assertIn("revive", json.loads(verbs_json2))

        # Config sub-keys
        cfg_json = main.get_autocomplete_suggestions("config ")
        self.assertIn("retention", json.loads(cfg_json))

        # Themes
    def test_multi_day_absence_streak_reset(self):
        """Verify multi-day absence (gap >= 2) resets streak to 0."""
        bridge.iso_date = "2026-09-15"
        todos = [{"id": "1", "uuid": "u1", "title": "Done Task", "task_date": "2026-09-15", "done": True, "subtasks": []}]
        main.save_local_todos(todos)

        # Advance to Sept 16 -> streak = 1
        bridge.iso_date = "2026-09-16"
        main.enforce_day_rollover()
        self.assertEqual(main.get_streak_data()["current_streak"], 1)

        # User closes tab and comes back on Sept 19 (3 days later)
        bridge.iso_date = "2026-09-19"
        main.enforce_day_rollover()
        self.assertEqual(main.get_streak_data()["current_streak"], 0)
        self.assertEqual(main.get_streak_data()["highest_streak"], 1)

    def test_retention_window_sliding_pruning(self):
        """Verify history only holds items within configured retention window."""
        bridge.iso_date = "2026-09-20"
        main.set_retention_days(3)

        # History has entries across 5 days
        hist = {
            "2026-09-15": [{"id": "1", "title": "Old 15"}],
            "2026-09-16": [{"id": "1", "title": "Old 16"}],
            "2026-09-17": [{"id": "1", "title": "Keep 17"}],
            "2026-09-18": [{"id": "1", "title": "Keep 18"}],
            "2026-09-19": [{"id": "1", "title": "Keep 19"}]
        }
        main.save_history_todos(hist)

        main.enforce_day_rollover()
        after = main.get_history_todos()

        # With retention=3 and today=2026-09-20, cutoff is 2026-09-17
        self.assertNotIn("2026-09-15", after)
        self.assertNotIn("2026-09-16", after)
        self.assertIn("2026-09-17", after)
        self.assertIn("2026-09-18", after)
        self.assertIn("2026-09-19", after)

    def test_revive_with_subtask_hierarchy(self):
        """Verify subtasks are preserved, given child dot IDs, and reset to incomplete."""
        bridge.iso_date = "2026-09-20"
        hist = {
            "2026-09-19": [
                {
                    "id": "1",
                    "uuid": "old-uuid",
                    "title": "Complex Parent",
                    "task_date": "2026-09-19",
                    "done": False,
                    "subtasks": [
                        {"id": "1.1", "title": "Sub A", "done": True},
                        {"id": "1.2", "title": "Sub B", "done": False}
                    ]
                }
            ]
        }
        main.save_history_todos(hist)
        main.save_local_todos([
            {"id": "1", "uuid": "cur-1", "title": "Current Active", "task_date": "2026-09-20", "done": False, "subtasks": []}
        ])

        # Revive H1
        res = main.cli_revive(["H1"])
        self.assertIn("Resurrected task to today's active list", res)

        todos = main.get_local_todos()
        self.assertEqual(len(todos), 2)
        revived = todos[1]
        self.assertEqual(revived["id"], "2")
        self.assertEqual(len(revived["subtasks"]), 2)
        self.assertEqual(revived["subtasks"][0]["id"], "2.1")
        self.assertEqual(revived["subtasks"][0]["title"], "Sub A")
        self.assertFalse(revived["subtasks"][0]["done"])
        self.assertEqual(revived["subtasks"][1]["id"], "2.2")
        self.assertFalse(revived["subtasks"][1]["done"])

    async def async_test_handle_command_dispatch(self):
        """Verify handle_command routes new commands and triggers synchronous rollover."""
        bridge.iso_date = "2026-09-20"
        res_streak = await main.handle_command("streak")
        self.assertIn("DISCIPLINE STREAK ENGINE", res_streak)

        res_theme = await main.handle_command("theme nord")
        self.assertIn("Theme switched to 'nord'", res_theme)
        self.assertEqual(bridge.theme, "nord")

        res_config = await main.handle_command("config retention 4")
        self.assertIn("Overdue retention window set to 4 days", res_config)
        self.assertEqual(main.get_retention_days(), 4)

    def test_handle_command_dispatch_sync(self):
        import asyncio
        asyncio.run(self.async_test_handle_command_dispatch())

if __name__ == "__main__":
    unittest.main()
