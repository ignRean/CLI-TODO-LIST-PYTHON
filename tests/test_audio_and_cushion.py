import unittest
import sys
import os
from datetime import datetime, timezone, timedelta

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import mock environment from test_exhaustive_features
from tests.test_exhaustive_features import mock_win
import main

class TestAudioAndCushionTriggers(unittest.TestCase):
    def setUp(self):
        # Reset local storage and sounds
        mock_win.localStorage.clear()
        mock_win.PyTodoBridge.sounds_played.clear()
        mock_win.PyTodoBridge.iso_date = "2026-09-20"
        mock_win.Date.set_datetime(2026, 9, 20, 12, 0, 0)
        main.save_local_todos([])
        main.save_history_todos({})
        main.save_streak_data({
            "current_streak": 0,
            "highest_streak": 0,
            "last_evaluated_date": None,
            "history_log": {}
        })

    def test_cli_add_triggers_add_sound(self):
        res = main.cli_add(["Write", "Audio", "Engine"])
        self.assertIn("[+] Task added", res)
        self.assertIn("add", mock_win.PyTodoBridge.sounds_played)

    def test_cli_rm_triggers_rm_sound(self):
        main.cli_add(["Task", "To", "Delete"])
        mock_win.PyTodoBridge.sounds_played.clear()
        
        res = main.cli_rm(["1"])
        self.assertIn("[-] Task deleted", res)
        self.assertIn("rm", mock_win.PyTodoBridge.sounds_played)

    def test_cli_rm_subtask_triggers_rm_sound(self):
        main.cli_add(["Parent", "Task", "-s", "Child Subtask"])
        mock_win.PyTodoBridge.sounds_played.clear()
        
        res = main.cli_rm(["1.1"])
        self.assertIn("[-] Subtask removed", res)
        self.assertIn("rm", mock_win.PyTodoBridge.sounds_played)

    def test_cli_undone_triggers_undone_sound(self):
        main.cli_add(["Task", "To", "Undo"])
        main.cli_done(["1"])
        mock_win.PyTodoBridge.sounds_played.clear()
        
        res = main.cli_undone(["1"])
        self.assertIn("[○] Task reverted", res)
        self.assertIn("undone", mock_win.PyTodoBridge.sounds_played)

    def test_cli_undone_subtask_triggers_undone_sound(self):
        main.cli_add(["Parent", "-s", "Sub1"])
        main.cli_done(["1.1"])
        mock_win.PyTodoBridge.sounds_played.clear()
        
        res = main.cli_undone(["1.1"])
        self.assertIn("[○] Subtask reverted", res)
        self.assertIn("undone", mock_win.PyTodoBridge.sounds_played)

    def test_cli_done_partial_vs_celebration_100_percent(self):
        main.cli_add(["Task", "One"])
        main.cli_add(["Task", "Two"])
        mock_win.PyTodoBridge.sounds_played.clear()
        
        # Complete Task 1 (1 of 2 done -> should play "done")
        main.cli_done(["1"])
        self.assertIn("done", mock_win.PyTodoBridge.sounds_played)
        self.assertNotIn("celebration", mock_win.PyTodoBridge.sounds_played)
        
        mock_win.PyTodoBridge.sounds_played.clear()
        # Complete Task 2 (2 of 2 done -> 100% board clear -> should play "celebration"!)
        main.cli_done(["2"])
        self.assertIn("celebration", mock_win.PyTodoBridge.sounds_played)

    def test_cli_revive_triggers_revive_sound(self):
        # Place task in history
        history = {
            "2026-09-19": [{
                "id": "1",
                "uuid": "hist-uuid-1",
                "title": "Old Expired Task",
                "done": False,
                "subtasks": []
            }]
        }
        main.save_history_todos(history)
        mock_win.PyTodoBridge.sounds_played.clear()
        
        res = main.cli_revive(["H1"])
        self.assertIn("Resurrected task", res)
        self.assertIn("revive", mock_win.PyTodoBridge.sounds_played)

    def test_cli_theme_triggers_theme_sound(self):
        mock_win.PyTodoBridge.setTheme = lambda name: str(name)
        mock_win.PyTodoBridge.sounds_played.clear()
        
        res = main.cli_theme(["nord"])
        self.assertIn("Theme switched to 'nord'", res)
        self.assertIn("theme", mock_win.PyTodoBridge.sounds_played)

    def test_streak_rollover_triggers_streak_sound(self):
        # Place yesterday's tasks completed directly in local storage
        todos = [
            {"id": "1", "uuid": "u1", "title": "Done Yesterday", "task_date": "2026-09-19", "done": True, "subtasks": []}
        ]
        main.save_local_todos(todos)
        main.save_streak_data({
            "current_streak": 0,
            "highest_streak": 0,
            "last_evaluated_date": None,
            "history_log": {}
        })
        mock_win.PyTodoBridge.iso_date = "2026-09-20"
        mock_win.Date.set_datetime(2026, 9, 20, 8, 0, 0)
        mock_win.PyTodoBridge.sounds_played.clear()
        
        main.enforce_day_rollover()
        self.assertIn("streak", mock_win.PyTodoBridge.sounds_played)

    def test_cli_streak_ath_triggers_streak_sound(self):
        main.save_streak_data({
            "current_streak": 5,
            "highest_streak": 5,
            "last_evaluated_date": "2026-09-19",
            "history_log": {}
        })
        mock_win.PyTodoBridge.sounds_played.clear()
        res = main.cli_streak([])
        self.assertIn("DISCIPLINE STREAK ENGINE", res)
        self.assertIn("streak", mock_win.PyTodoBridge.sounds_played)

if __name__ == "__main__":
    unittest.main()
