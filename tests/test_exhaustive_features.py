"""
PhD Consortium Exhaustive Unit & Integration Test Suite for PyTodo CLI
Authors: Dr. Marcus Sterling (Lead Cybernetics & Red Teamer) & Dr. Aris Thorne (Chief Research Scientist)
Target: main.py
"""

import sys
import os
import json
import uuid
import re
import unittest
import types
import asyncio
from datetime import datetime, timezone, timedelta

# Ensure parent directory is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# ---------------------------------------------------------
# Mock Environment Setup (Pyodide & JS Bridge Interop)
# ---------------------------------------------------------

class MockStorage:
    def __init__(self):
        self.store = {}

    def getItem(self, key):
        return self.store.get(str(key))

    def setItem(self, key, value):
        self.store[str(key)] = str(value)

    def removeItem(self, key):
        self.store.pop(str(key), None)

    def clear(self):
        self.store.clear()


class MockPyTodoBridge:
    def __init__(self):
        self.step_sec = 300
        self.last_payload = None
        self.dashboard_mode = False
        self.terminal_cols = 80
        self.iso_date = "2026-09-19"
        self.sounds_played = []
        self.pairing_code = ""
        self.sync_status = "IDLE"
        self.sync_triggered = False

    def getFocusStep(self):
        return self.step_sec

    def setFocusStep(self, sec):
        self.step_sec = int(sec)

    def enterFocusMode(self, payload_str):
        self.last_payload = json.loads(payload_str)

    def triggerBackgroundSync(self):
        self.sync_triggered = True

    def playSound(self, name):
        self.sounds_played.append(name)

    def getTerminalCols(self):
        return self.terminal_cols

    def getLocalISODate(self):
        return self.iso_date

    def setPairingCode(self, code):
        self.pairing_code = str(code)

    def setSyncStatus(self, status):
        self.sync_status = str(status)


class MockDate:
    def __init__(self):
        # Default fixed midday timestamp on 2026-09-19 12:00:00 UTC
        self.set_datetime(2026, 9, 19, 12, 0, 0)
        self._offset = 0

    def set_datetime(self, year, month, day, hour=12, minute=0, second=0):
        dt = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
        self._now_ts = int(dt.timestamp() * 1000)

    def now(self):
        return self._now_ts

    def new(self):
        offset = self._offset
        return type("DateObj", (), {
            "getTimezoneOffset": lambda s: offset
        })()


class MockWindow:
    def __init__(self):
        self.localStorage = MockStorage()
        self.PyTodoBridge = MockPyTodoBridge()
        self.Date = MockDate()
        self.term = type("Term", (), {"cols": 80})()


mock_win = MockWindow()
js_mock = types.ModuleType("js")
js_mock.window = mock_win
js_mock.supabaseClient = None
sys.modules["js"] = js_mock

# Import main after setting up the js mock module
from main import (
    sanitize_text,
    is_wide_or_emoji,
    get_visual_width,
    truncate_visual,
    get_terminal_width,
    pad_string,
    get_local_now,
    get_local_date_str,
    get_pairing_code,
    set_pairing_code,
    get_local_todos,
    save_local_todos,
    purge_expired_tasks,
    parse_duration_seconds,
    parse_duration,
    parse_due_input,
    parse_due_time,
    get_deadline_info,
    cli_add,
    cli_ls,
    cli_done,
    cli_undone,
    cli_edit,
    cli_subtask,
    cli_rm,
    cli_config,
    handle_focus_step_command,
    cli_link,
    cli_unlink,
    get_autocomplete_suggestions,
    check_midnight_wipe,
    handle_command,
    COMMANDS,
    C_RESET,
    C_GREEN,
    C_YELLOW,
    C_RED,
    C_CYAN,
    C_GRAY,
    C_ORANGE,
    C_B_YELLOW,
    C_B_BLINK_RED,
    C_INV_RED
)


class BasePyTodoTest(unittest.TestCase):
    def setUp(self):
        mock_win.localStorage.clear()
        mock_win.PyTodoBridge.step_sec = 300
        mock_win.PyTodoBridge.last_payload = None
        mock_win.PyTodoBridge.terminal_cols = 80
        mock_win.PyTodoBridge.iso_date = "2026-09-19"
        mock_win.PyTodoBridge.sounds_played.clear()
        mock_win.PyTodoBridge.pairing_code = ""
        mock_win.PyTodoBridge.sync_status = "IDLE"
        mock_win.PyTodoBridge.sync_triggered = False
        mock_win.Date.set_datetime(2026, 9, 19, 12, 0, 0)
        save_local_todos([])
        set_pairing_code("")

    def run_cmd(self, line: str) -> str:
        """Helper to run async handle_command synchronously."""
        return asyncio.run(handle_command(line))


# ---------------------------------------------------------
# 1. Command Parsing & Error Handling
# ---------------------------------------------------------

class TestCommandParsingAndErrorHandling(BasePyTodoTest):
    def test_invalid_command_verbs(self):
        res = self.run_cmd("invalidverb123")
        clean = sanitize_text(res)
        self.assertIn("Unknown command: 'invalidverb123'", clean)
        self.assertIn("Type 'help' for options", clean)

    def test_empty_and_whitespace_inputs(self):
        self.assertEqual(self.run_cmd(""), "")
        self.assertEqual(self.run_cmd("   "), "")
        self.assertEqual(self.run_cmd("\t  \n"), "")

    def test_syntax_error_unclosed_quotes(self):
        res = self.run_cmd('add "Unclosed task title')
        clean = sanitize_text(res)
        self.assertIn("Syntax Error", clean)
        self.assertIn("closing quotation", clean.lower())

    def test_quoted_arguments_with_spaces_and_special_chars(self):
        res = self.run_cmd('add "Deploy Service (v2.1)" --due "6:30 pm" --duration "1h 15m" -s "Verify health"')
        clean = sanitize_text(res)
        self.assertIn("[+] Task added:", clean)
        self.assertIn("Deploy Service (v2.1)", clean)
        todos = get_local_todos()
        self.assertEqual(len(todos), 1)
        self.assertEqual(todos[0]["title"], "Deploy Service (v2.1)")
        self.assertEqual(todos[0]["due_time"], "18:30")
        self.assertEqual(todos[0]["duration_minutes"], 75)
        self.assertEqual(len(todos[0]["subtasks"]), 1)
        self.assertEqual(todos[0]["subtasks"][0]["title"], "Verify health")

    def test_missing_required_arguments(self):
        # add without title
        self.assertIn("Task title required", sanitize_text(self.run_cmd("add")))
        self.assertIn("Task title required", sanitize_text(self.run_cmd("add --due 18:00")))

        # done without ID
        self.assertIn("Task or subtask ID required", sanitize_text(self.run_cmd("done")))

        # undone without ID
        self.assertIn("Task or subtask ID required", sanitize_text(self.run_cmd("undone")))

        # edit without ID
        self.assertIn("Task ID required", sanitize_text(self.run_cmd("edit")))

        # rm without ID
        self.assertIn("Task or subtask ID required", sanitize_text(self.run_cmd("rm")))

        # subtask without args
        self.assertIn("Usage: subtask <id> <subtask_title>", sanitize_text(self.run_cmd("subtask")))
        self.assertIn("Usage: subtask <id> <subtask_title>", sanitize_text(self.run_cmd("subtask 1")))

    def test_screen_clear_commands(self):
        self.assertEqual(self.run_cmd("clear"), "__CLEAR_SCREEN__")
        self.assertEqual(self.run_cmd("c"), "__CLEAR_SCREEN__")
        self.assertEqual(self.run_cmd("cls"), "__CLEAR_SCREEN__")

    def test_help_commands(self):
        help_out = sanitize_text(self.run_cmd("help"))
        self.assertIn("PyTodo Commands:", help_out)
        self.assertIn("add (or a)", help_out)
        self.assertIn("ls (or l / today)", help_out)
        self.assertIn("focus", help_out)

        h_out = sanitize_text(self.run_cmd("h"))
        self.assertEqual(help_out, h_out)


# ---------------------------------------------------------
# 2. Task Addition with Varied Due Times & Durations
# ---------------------------------------------------------

class TestTaskAdditionDueAndDuration(BasePyTodoTest):
    def test_varied_due_times(self):
        cases = [
            ("18:30", "18:30"),
            ("6pm", "18:00"),
            ("6:00pm", "18:00"),
            ("6:00 pm", "18:00"),
            ("11:45 PM", "23:45"),
            ("12am", "00:00"),
            ("12:00am", "00:00"),
            ("12pm", "12:00"),
            ("12:30pm", "12:30"),
            ("09:15", "09:15"),
            ("9:15 am", "09:15")
        ]
        for due_in, expected in cases:
            res = self.run_cmd(f'add "Task {due_in}" --due "{due_in}"')
            clean = sanitize_text(res)
            self.assertIn("[+] Task added:", clean)
            self.assertIn(f"Due: {expected}", clean)

        todos = get_local_todos()
        self.assertEqual(len(todos), len(cases))
        for t, (_, expected) in zip(todos, cases):
            self.assertEqual(t["due_time"], expected)

    def test_invalid_due_formats(self):
        invalid_cases = ["invalid", "25:00", "14:75", "99pm", "now", ""]
        for inv in invalid_cases:
            res = self.run_cmd(f'add "Task Invalid Due" --due "{inv}"')
            clean = sanitize_text(res)
            self.assertIn("Error: Invalid due time format", clean)

        self.assertEqual(len(get_local_todos()), 0)

    def test_varied_durations(self):
        cases = [
            ("45m", 45),
            ("1h", 60),
            ("1h30m", 90),
            ("1h 15m", 75),
            ("2.5h", 150),
            ("30s", 1),       # 30s rounds to 1m
            ("90s", 2),       # 90s rounds to 2m
            ("25", 25),       # Plain number defaults to minutes
            ("0.5h", 30)
        ]
        for dur_in, expected_min in cases:
            res = self.run_cmd(f'add "Task {dur_in}" --duration "{dur_in}"')
            clean = sanitize_text(res)
            self.assertIn("[+] Task added:", clean)
            self.assertIn(f"Est: {expected_min}m", clean)

        todos = get_local_todos()
        self.assertEqual(len(todos), len(cases))
        for t, (_, expected_min) in zip(todos, cases):
            self.assertEqual(t["duration_minutes"], expected_min)

    def test_invalid_durations(self):
        invalid_cases = ["invalid", "-10m", "-1h", "0m", "0s", "abc", "m10"]
        for inv in invalid_cases:
            res = self.run_cmd(f'add "Task Invalid Dur" --duration "{inv}"')
            clean = sanitize_text(res)
            self.assertIn("Error: Invalid duration format", clean)

        self.assertEqual(len(get_local_todos()), 0)

    def test_micro_alias_a(self):
        res = self.run_cmd('a "Micro Task" --due 14:00 --duration 20m')
        clean = sanitize_text(res)
        self.assertIn("[+] Task added:", clean)
        todos = get_local_todos()
        self.assertEqual(len(todos), 1)
        self.assertEqual(todos[0]["title"], "Micro Task")


# ---------------------------------------------------------
# 3. Subtasks Lifecycle & Re-indexing
# ---------------------------------------------------------

class TestSubtasksLifecycleAndReindexing(BasePyTodoTest):
    def test_add_with_multiple_subtasks_flags(self):
        res = self.run_cmd('add "Build Auth Module" -s "Design JWT schema" --sub "Implement refresh tokens" --subtask "Add rate limiter"')
        clean = sanitize_text(res)
        self.assertIn("[+] Task added:", clean)
        self.assertIn("[1.1] Design JWT schema", clean)
        self.assertIn("[1.2] Implement refresh tokens", clean)
        self.assertIn("[1.3] Add rate limiter", clean)

        todos = get_local_todos()
        self.assertEqual(len(todos), 1)
        subtasks = todos[0]["subtasks"]
        self.assertEqual(len(subtasks), 3)
        self.assertEqual(subtasks[0]["id"], "1.1")
        self.assertEqual(subtasks[1]["id"], "1.2")
        self.assertEqual(subtasks[2]["id"], "1.3")

    def test_add_subtask_via_cli_subtask_command(self):
        self.run_cmd('add "Main Task"')
        res = self.run_cmd('subtask 1 "First Subtask"')
        clean = sanitize_text(res)
        self.assertIn("Task '1' updated:", clean)
        self.assertIn("added subtask [1.1]", clean)

        res2 = self.run_cmd('add-sub 1 "Second Subtask"')
        clean2 = sanitize_text(res2)
        self.assertIn("added subtask [1.2]", clean2)

        # Shortcut alias 's'
        res3 = self.run_cmd('s 1 "Third Subtask"')
        clean3 = sanitize_text(res3)
        self.assertIn("added subtask [1.3]", clean3)

        todos = get_local_todos()
        subs = todos[0]["subtasks"]
        self.assertEqual(len(subs), 3)
        self.assertEqual([s["id"] for s in subs], ["1.1", "1.2", "1.3"])
        self.assertEqual([s["title"] for s in subs], ["First Subtask", "Second Subtask", "Third Subtask"])

    def test_delete_subtask_via_edit_rm_sub_and_reindex(self):
        self.run_cmd('add "Project" -s "Sub A" -s "Sub B" -s "Sub C" -s "Sub D"')
        todos = get_local_todos()
        self.assertEqual(len(todos[0]["subtasks"]), 4)

        # Remove subtask at index 2 (Sub B) using number
        res = self.run_cmd('edit 1 --rm-sub 2')
        clean = sanitize_text(res)
        self.assertIn("removed subtask 'Sub B'", clean)

        todos = get_local_todos()
        subs = todos[0]["subtasks"]
        self.assertEqual(len(subs), 3)
        self.assertEqual([s["id"] for s in subs], ["1.1", "1.2", "1.3"])
        self.assertEqual([s["title"] for s in subs], ["Sub A", "Sub C", "Sub D"])

        # Remove subtask using full ID string '1.2' (which is now Sub C)
        res2 = self.run_cmd('edit 1 --rm-sub 1.2')
        clean2 = sanitize_text(res2)
        self.assertIn("removed subtask 'Sub C'", clean2)

        todos = get_local_todos()
        subs = todos[0]["subtasks"]
        self.assertEqual(len(subs), 2)
        self.assertEqual([s["id"] for s in subs], ["1.1", "1.2"])
        self.assertEqual([s["title"] for s in subs], ["Sub A", "Sub D"])

    def test_delete_subtask_via_rm_command_and_reindex(self):
        self.run_cmd('add "Architecture" -s "Component 1" -s "Component 2" -s "Component 3"')

        # Remove subtask 1.2 using rm
        res = self.run_cmd('rm 1.2')
        clean = sanitize_text(res)
        self.assertIn("Subtask removed: [1.2] Component 2", clean)

        todos = get_local_todos()
        subs = todos[0]["subtasks"]
        self.assertEqual(len(subs), 2)
        self.assertEqual(subs[0]["id"], "1.1")
        self.assertEqual(subs[0]["title"], "Component 1")
        self.assertEqual(subs[1]["id"], "1.2")
        self.assertEqual(subs[1]["title"], "Component 3")

    def test_subtask_error_handling(self):
        # Non-existent parent task
        self.assertIn("Error: Task ID '99' not found", sanitize_text(self.run_cmd('subtask 99 "Invalid"')))
        # Non-existent subtask for removal
        self.run_cmd('add "Test"')
        self.assertIn("Subtask '9' not found", sanitize_text(self.run_cmd('edit 1 --rm-sub 9')))
        self.assertIn("Subtask '1.9' not found", sanitize_text(self.run_cmd('rm 1.9')))


# ---------------------------------------------------------
# 4. Completion Cascading
# ---------------------------------------------------------

class TestCompletionCascading(BasePyTodoTest):
    def test_subtask_completion_auto_completes_parent_when_all_done(self):
        self.run_cmd('add "Module Testing" -s "Unit Tests" -s "Integration Tests"')

        # Done with first subtask
        res1 = self.run_cmd('done 1.1')
        clean1 = sanitize_text(res1)
        self.assertIn("Subtask completed: [1.1] Unit Tests", clean1)

        todos = get_local_todos()
        task = todos[0]
        self.assertTrue(task["subtasks"][0]["done"])
        self.assertFalse(task["subtasks"][1]["done"])
        self.assertFalse(task["done"])

        # Done with second subtask -> all subtasks done -> parent auto-completes!
        res2 = self.run_cmd('done 1.2')
        clean2 = sanitize_text(res2)
        self.assertIn("Subtask completed: [1.2] Integration Tests", clean2)

        todos = get_local_todos()
        task = todos[0]
        self.assertTrue(task["subtasks"][0]["done"])
        self.assertTrue(task["subtasks"][1]["done"])
        self.assertTrue(task["done"], "Parent task should auto-complete when all subtasks are done")

    def test_reverting_subtask_uncompletes_parent(self):
        self.run_cmd('add "Review PR" -s "Check diff" -s "Run linter"')
        self.run_cmd('done 1.1')
        self.run_cmd('done 1.2')

        # Parent is now done
        self.assertTrue(get_local_todos()[0]["done"])

        # Revert subtask 1.1 -> parent must uncomplete
        res = self.run_cmd('undone 1.1')
        clean = sanitize_text(res)
        self.assertIn("Subtask reverted to incomplete: [1.1]", clean)

        todos = get_local_todos()
        task = todos[0]
        self.assertFalse(task["subtasks"][0]["done"])
        self.assertTrue(task["subtasks"][1]["done"])
        self.assertFalse(task["done"], "Parent task should revert to incomplete when any subtask is reverted")

    def test_done_parent_cascades_to_all_subtasks(self):
        self.run_cmd('add "Milestone 1" -s "Phase A" -s "Phase B"')
        res = self.run_cmd('done 1')
        clean = sanitize_text(res)
        self.assertIn("Task completed: [1] Milestone 1", clean)

        todos = get_local_todos()
        task = todos[0]
        self.assertTrue(task["done"])
        self.assertTrue(all(s["done"] for s in task["subtasks"]), "All subtasks should be marked done when parent is completed")

    def test_undone_parent_reverts_all_subtasks(self):
        self.run_cmd('add "Milestone 2" -s "Step 1" -s "Step 2"')
        self.run_cmd('done 1')

        # Both parent and subtasks are done
        self.assertTrue(get_local_todos()[0]["done"])
        self.assertTrue(all(s["done"] for s in get_local_todos()[0]["subtasks"]))

        # Undone parent
        res = self.run_cmd('undone 1')
        clean = sanitize_text(res)
        self.assertIn("Task reverted to incomplete: [1]", clean)

        todos = get_local_todos()
        task = todos[0]
        self.assertFalse(task["done"], "Parent task should be marked incomplete")
        self.assertFalse(any(s["done"] for s in task["subtasks"]), "All subtasks should be marked incomplete when parent is reverted")

    def test_space_notation_for_subtask_done_and_undone(self):
        self.run_cmd('add "Space Notation Task" -s "Sub 1"')
        # done 1 1 -> done 1.1
        res = self.run_cmd('done 1 1')
        clean = sanitize_text(res)
        self.assertIn("Subtask completed: [1.1]", clean)
        self.assertTrue(get_local_todos()[0]["subtasks"][0]["done"])

        # undone 1 1 -> undone 1.1
        res2 = self.run_cmd('undone 1 1')
        clean2 = sanitize_text(res2)
        self.assertIn("Subtask reverted to incomplete: [1.1]", clean2)
        self.assertFalse(get_local_todos()[0]["subtasks"][0]["done"])

    def test_multi_target_done(self):
        self.run_cmd('add "Multi Target" -s "Sub A" -s "Sub B" -s "Sub C"')
        res = self.run_cmd('done 1.1 1.3')
        clean = sanitize_text(res)
        self.assertIn("Subtask completed: [1.1]", clean)
        self.assertIn("Subtask completed: [1.3]", clean)

        subs = get_local_todos()[0]["subtasks"]
        self.assertTrue(subs[0]["done"])
        self.assertFalse(subs[1]["done"])
        self.assertTrue(subs[2]["done"])


# ---------------------------------------------------------
# 5. Editing Tasks
# ---------------------------------------------------------

class TestEditingTasks(BasePyTodoTest):
    def test_edit_title_with_and_without_flag(self):
        self.run_cmd('add "Old Title"')
        # With flag
        res1 = self.run_cmd('edit 1 --title "New Title via Flag"')
        clean1 = sanitize_text(res1)
        self.assertIn("title -> 'New Title via Flag'", clean1)
        self.assertEqual(get_local_todos()[0]["title"], "New Title via Flag")

        # Without flag
        res2 = self.run_cmd('edit 1 Positional New Title')
        clean2 = sanitize_text(res2)
        self.assertIn("title -> 'Positional New Title'", clean2)
        self.assertEqual(get_local_todos()[0]["title"], "Positional New Title")

    def test_edit_due_and_clear_due(self):
        self.run_cmd('add "Due Test"')
        res = self.run_cmd('edit 1 --due 17:45')
        clean = sanitize_text(res)
        self.assertIn("due -> 17:45", clean)
        self.assertEqual(get_local_todos()[0]["due_time"], "17:45")

        # Clear due
        res_clear = self.run_cmd('edit 1 --clear-due')
        clean_clear = sanitize_text(res_clear)
        self.assertIn("due cleared", clean_clear)
        self.assertIsNone(get_local_todos()[0]["due_time"])

    def test_edit_duration_and_clear_duration(self):
        self.run_cmd('add "Dur Test"')
        res = self.run_cmd('edit 1 --duration 1h30m')
        clean = sanitize_text(res)
        self.assertIn("duration -> 90m", clean)
        self.assertEqual(get_local_todos()[0]["duration_minutes"], 90)

        # Clear duration
        res_clear = self.run_cmd('edit 1 --clear-duration')
        clean_clear = sanitize_text(res_clear)
        self.assertIn("duration cleared", clean_clear)
        self.assertIsNone(get_local_todos()[0]["duration_minutes"])

    def test_edit_subtask_title_directly(self):
        self.run_cmd('add "Parent" -s "Initial Sub"')
        res = self.run_cmd('edit 1.1 "Updated Subtask Title"')
        clean = sanitize_text(res)
        self.assertIn("Subtask '1.1' updated: title -> 'Updated Subtask Title'", clean)
        self.assertEqual(get_local_todos()[0]["subtasks"][0]["title"], "Updated Subtask Title")

    def test_edit_error_conditions(self):
        # Non-existent task
        self.assertIn("Task ID '999' not found", sanitize_text(self.run_cmd('edit 999 --title "X"')))
        # Non-existent subtask
        self.run_cmd('add "Task"')
        self.assertIn("Subtask '1.99' not found", sanitize_text(self.run_cmd('edit 1.99 --title "X"')))
        # Invalid due format
        self.assertIn("Invalid due format", sanitize_text(self.run_cmd('edit 1 --due "badtime"')))
        # Invalid duration
        self.assertIn("Invalid duration", sanitize_text(self.run_cmd('edit 1 --duration "baddur"')))
        # No changes specified
        self.assertIn("No changes specified", sanitize_text(self.run_cmd('edit 1')))


# ---------------------------------------------------------
# 6. Deletion (Task & Subtask)
# ---------------------------------------------------------

class TestTaskDeletion(BasePyTodoTest):
    def test_delete_main_task(self):
        self.run_cmd('add "Task 1"')
        self.run_cmd('add "Task 2"')
        self.assertEqual(len(get_local_todos()), 2)

        res = self.run_cmd('rm 1')
        clean = sanitize_text(res)
        self.assertIn("Task deleted: [1] Task 1", clean)
        todos = get_local_todos()
        self.assertEqual(len(todos), 1)
        self.assertEqual(todos[0]["id"], "2")

    def test_delete_via_del_and_delete_aliases(self):
        self.run_cmd('add "Task A"')
        self.run_cmd('add "Task B"')
        res_del = self.run_cmd('del 1')
        clean_del = sanitize_text(res_del)
        self.assertIn("Task deleted: [1] Task A", clean_del)

        res_delete = self.run_cmd('delete 2')
        clean_delete = sanitize_text(res_delete)
        self.assertIn("Task deleted: [2] Task B", clean_delete)
        self.assertEqual(len(get_local_todos()), 0)

    def test_delete_subtask_by_id(self):
        self.run_cmd('add "Task" -s "Sub 1" -s "Sub 2"')
        res = self.run_cmd('rm 1.1')
        clean = sanitize_text(res)
        self.assertIn("Subtask removed: [1.1] Sub 1", clean)

        todos = get_local_todos()
        subs = todos[0]["subtasks"]
        self.assertEqual(len(subs), 1)
        self.assertEqual(subs[0]["id"], "1.1")
        self.assertEqual(subs[0]["title"], "Sub 2")

    def test_delete_non_existent_ids(self):
        self.assertIn("Task ID '404' not found", sanitize_text(self.run_cmd('rm 404')))
        self.run_cmd('add "Task"')
        self.assertIn("Subtask '1.404' not found", sanitize_text(self.run_cmd('rm 1.404')))


# ---------------------------------------------------------
# 7. Midnight Wipe Invariant
# ---------------------------------------------------------

class TestMidnightWipeInvariant(BasePyTodoTest):
    def test_purge_expired_tasks_rollover(self):
        mock_win.PyTodoBridge.iso_date = "2026-09-19"
        mock_win.Date.set_datetime(2026, 9, 19, 12, 0, 0)

        # Task 1: Incomplete task created today
        self.run_cmd('add "Today Incomplete Task"')
        # Task 2: Completed task created today
        self.run_cmd('add "Today Completed Task"')
        self.run_cmd('done 2')

        # Add yesterday's tasks directly
        todos = get_local_todos()
        todos.append({
            "id": "3",
            "uuid": "yesterday-incomplete-uuid",
            "pairing_code": "",
            "task_date": "2026-09-18",
            "title": "Yesterday Incomplete Task",
            "done": False,
            "subtasks": [],
            "created_at": "2026-09-18T10:00:00Z",
            "updated_at": "2026-09-18T10:00:00Z",
            "synced": True
        })
        todos.append({
            "id": "4",
            "uuid": "yesterday-completed-uuid",
            "pairing_code": "",
            "task_date": "2026-09-18",
            "title": "Yesterday Completed Task",
            "done": True,
            "subtasks": [],
            "created_at": "2026-09-18T10:00:00Z",
            "updated_at": "2026-09-18T10:00:00Z",
            "synced": True
        })
        save_local_todos(todos)
        self.assertEqual(len(get_local_todos()), 4)

        # Before rollover, purging for 2026-09-19 purges the 2 tasks from 2026-09-18
        wiped = purge_expired_tasks()
        self.assertEqual(wiped, 1, "Only 1 incomplete task from 2026-09-18 should be counted as wiped")
        active = get_local_todos()
        self.assertEqual(len(active), 2)
        self.assertEqual([t["id"] for t in active], ["1", "2"])

        # Now advance mock date from today to tomorrow: 2026-09-19 -> 2026-09-20
        mock_win.PyTodoBridge.iso_date = "2026-09-20"
        mock_win.Date.set_datetime(2026, 9, 20, 8, 0, 0)

        # Run check_midnight_wipe() on date roll
        wiped_rollover = check_midnight_wipe()
        self.assertEqual(wiped_rollover, 1, "Task 1 was incomplete and should be counted as wiped")

        # Add a fresh task for tomorrow
        self.run_cmd('add "Tomorrow Morning Task"')

        active_new_day = get_local_todos()
        self.assertEqual(len(active_new_day), 1)
        self.assertEqual(active_new_day[0]["title"], "Tomorrow Morning Task")
        self.assertEqual(active_new_day[0]["task_date"], "2026-09-20")


# ---------------------------------------------------------
# 8. Device Pairing & Link / Unlink
# ---------------------------------------------------------

class TestDevicePairingAndLink(BasePyTodoTest):
    def test_link_status_unlinked(self):
        res = self.run_cmd('link status')
        clean = sanitize_text(res)
        self.assertIn("Not linked to any device", clean)

    def test_link_generate(self):
        res = self.run_cmd('link generate')
        clean = sanitize_text(res)
        self.assertIn("Pairing key generated:", clean)

        code = get_pairing_code()
        self.assertIsNotNone(code)
        self.assertTrue(re.match(r'^\d{6}$', code), f"Generated code '{code}' must be 6 digits")

        # Status should now reflect the pairing key
        st = self.run_cmd('link status')
        clean_st = sanitize_text(st)
        self.assertIn(f"Linked to Pairing Key: {code}", clean_st)

    def test_link_with_specific_code(self):
        res = self.run_cmd('link 654321')
        clean = sanitize_text(res)
        self.assertIn("Successfully linked to key", clean)
        self.assertIn("654321", clean)
        self.assertEqual(get_pairing_code(), "654321")

    def test_link_invalid_code(self):
        res1 = self.run_cmd('link abc')
        clean1 = sanitize_text(res1)
        self.assertIn("Error: Pairing key must be a 6 to 8 digit code", clean1)

        res2 = self.run_cmd('link 1234')
        clean2 = sanitize_text(res2)
        self.assertIn("Error: Pairing key must be a 6 to 8 digit code", clean2)

    def test_unlink_command(self):
        self.run_cmd('link 888999')
        self.assertEqual(get_pairing_code(), "888999")

        # Execute 'unlink' as top-level verb
        res = self.run_cmd('unlink')
        clean = sanitize_text(res)
        self.assertIn("Device unlinked. Tasks will remain local-only.", clean)
        self.assertIsNone(get_pairing_code())

        # Also test 'link unlink'
        self.run_cmd('link 888999')
        res2 = self.run_cmd('link unlink')
        clean2 = sanitize_text(res2)
        self.assertIn("Device unlinked", clean2)
        self.assertIsNone(get_pairing_code())


# ---------------------------------------------------------
# 9. Heatmap & Responsive Stream Modes (Wide vs Narrow)
# ---------------------------------------------------------

class TestHeatmapAndResponsiveStreamModes(BasePyTodoTest):
    def setUp(self):
        super().setUp()
        mock_win.PyTodoBridge.iso_date = "2026-09-19"
        mock_win.Date.set_datetime(2026, 9, 19, 12, 0, 0)
        self.run_cmd('add "Task Standard" --due 22:00 --duration 45m -s "Sub Alpha"')

    def test_wide_mode_terminal(self):
        mock_win.PyTodoBridge.terminal_cols = 100
        output = cli_ls([])
        clean = sanitize_text(output)

        # Table header must be present in wide mode
        self.assertIn("ID    STATUS   SYNC  DEADLINE / HEATMAP    TASK", clean)
        self.assertIn("to Midnight", clean)
        self.assertIn("1     [TODO]", clean)
        # Subtask hierarchy branch
        self.assertIn("└──", clean)
        self.assertIn("Sub Alpha", clean)

    def test_narrow_mode_terminal(self):
        mock_win.PyTodoBridge.terminal_cols = 60
        output = cli_ls([])
        clean = sanitize_text(output)

        # Table header must NOT be present in mobile compact stream mode
        self.assertNotIn("ID    STATUS   SYNC  DEADLINE / HEATMAP    TASK", clean)
        # Mobile stacked format: [1] [TODO] Task Standard ... Due: ... Sync: ...
        self.assertIn("[1] [TODO] Task Standard", clean)
        self.assertIn("Due:", clean)
        self.assertIn("Sync:", clean)
        self.assertIn("└──", clean)

    def test_deadline_color_and_tag_heuristics(self):
        # Base task template
        task = {
            "id": "1",
            "title": "Timed Task",
            "task_date": "2026-09-19",
            "done": False,
            "created_at": "2026-09-19T08:00:00"
        }

        # 1. Done task
        task_done = dict(task, done=True)
        _, tag, color = get_deadline_info(task_done)
        self.assertEqual(tag, "DONE")
        self.assertEqual(color, C_GRAY)

        # 2. Untimed task for today during calm midday (12:00)
        task_untimed = dict(task, due_time=None)
        _, tag, color = get_deadline_info(task_untimed)
        self.assertEqual(tag, "-")
        self.assertEqual(color, C_GRAY)

        # 3. Calm Green (>3h): Due 22:00 (10h left)
        task_calm = dict(task, due_time="22:00")
        diff, tag, color = get_deadline_info(task_calm)
        self.assertGreater(diff, 10800)
        self.assertEqual(color, C_GREEN)

        # 4. Soon Warning Yellow (<=3h): Due 14:00 (2h left)
        task_soon = dict(task, due_time="14:00")
        diff, tag, color = get_deadline_info(task_soon)
        self.assertIn("SOON: 2h 0m", tag)
        self.assertEqual(color, C_B_YELLOW)

        # 5. Urgent Orange (<=1h30m): Due 13:00 (1h left)
        task_urgent = dict(task, due_time="13:00")
        diff, tag, color = get_deadline_info(task_urgent)
        self.assertIn("URGENT: 1h 0m", tag)
        self.assertEqual(color, C_ORANGE)

        # 6. Critical Red (<=45m): Due 12:30 (30m left)
        task_crit = dict(task, due_time="12:30")
        diff, tag, color = get_deadline_info(task_crit)
        self.assertIn("CRITICAL: 30m LEFT", tag)
        self.assertEqual(color, C_B_BLINK_RED)

        # 7. Overdue Inverted Red (<0m): Due 11:00 (60m ago)
        task_overdue = dict(task, due_time="11:00")
        diff, tag, color = get_deadline_info(task_overdue)
        self.assertLess(diff, 0)
        self.assertIn("OVERDUE: 60m AGO", tag)
        self.assertEqual(color, C_INV_RED)

    def test_untimed_task_midnight_progression(self):
        """Verifies untimed tasks follow pure absolute countdown to midnight without percentage glitches."""
        untimed = {
            "id": "1",
            "title": "Untimed Commitment",
            "task_date": "2026-09-19",
            "due_time": None,
            "created_at": "2026-09-19T08:00:00",
            "done": False
        }

        # A. At 12:00 (12h to midnight) -> Calm '-'
        mock_win.Date.set_datetime(2026, 9, 19, 12, 0, 0)
        _, tag, color = get_deadline_info(untimed)
        self.assertEqual(tag, "-")
        self.assertEqual(color, C_GRAY)

        # B. At 22:27 (92-93m to midnight) -> SOON in Yellow (NOT Critical!)
        mock_win.Date.set_datetime(2026, 9, 19, 22, 27, 0)
        diff, tag, color = get_deadline_info(untimed)
        self.assertGreater(diff, 5400)
        self.assertIn("SOON: 1h 32m", tag)
        self.assertEqual(color, C_B_YELLOW)

        # C. At 22:30 (90m to midnight) -> URGENT in Orange (NOT Critical!)
        mock_win.Date.set_datetime(2026, 9, 19, 22, 30, 0)
        diff, tag, color = get_deadline_info(untimed)
        self.assertLessEqual(diff, 5400)
        self.assertGreater(diff, 2700)
        self.assertIn("URGENT: 1h 29m", tag)
        self.assertEqual(color, C_ORANGE)

        # D. At 23:20 (39-40m to midnight) -> CRITICAL in Blinking Red
        mock_win.Date.set_datetime(2026, 9, 19, 23, 20, 0)
        diff, tag, color = get_deadline_info(untimed)
        self.assertLessEqual(diff, 2700)
        self.assertIn("CRITICAL: 39m LEFT", tag)
        self.assertEqual(color, C_B_BLINK_RED)

        # Reset clock
        mock_win.Date.set_datetime(2026, 9, 19, 12, 0, 0)

    def test_timed_task_hard_ceilings_and_micro_sprints(self):
        """Verifies timed tasks enforce hard ceilings so >45m left is never Critical."""
        # 1. Macro-task: Set at 08:00 due 23:30 (15.5h window)
        macro_task = {
            "id": "1",
            "title": "All Day Project",
            "task_date": "2026-09-19",
            "due_time": "23:30",
            "created_at": "2026-09-19T08:00:00",
            "done": False
        }
        # At 22:00, 90 minutes remaining (over 90% window elapsed):
        mock_win.Date.set_datetime(2026, 9, 19, 22, 0, 0)
        diff, tag, color = get_deadline_info(macro_task)
        # Must be URGENT (Orange), NEVER Critical!
        self.assertIn("URGENT: 1h 30m", tag)
        self.assertEqual(color, C_ORANGE)

        # 2. Micro-sprint: 30-minute task created at 12:00 due 12:30
        micro_task = {
            "id": "2",
            "title": "Quick Standup",
            "task_date": "2026-09-19",
            "due_time": "12:30",
            "created_at": "2026-09-19T12:00:00",
            "done": False
        }
        # At 12:00 (creation instant, 30m remaining):
        mock_win.Date.set_datetime(2026, 9, 19, 12, 0, 0)
        diff, tag, color = get_deadline_info(micro_task)
        # Must NOT be Critical on minute 0 of a 30m sprint!
        self.assertNotIn("CRITICAL", tag)
        self.assertEqual(color, C_B_YELLOW)

        # At 12:28 (2 minutes remaining, >90% elapsed):
        mock_win.Date.set_datetime(2026, 9, 19, 12, 28, 0)
        diff, tag, color = get_deadline_info(micro_task)
        self.assertIn("CRITICAL: 2m LEFT", tag)
        self.assertEqual(color, C_B_BLINK_RED)

        # Reset clock
        mock_win.Date.set_datetime(2026, 9, 19, 12, 0, 0)


# ---------------------------------------------------------
# 10. Terminal Input Sanitization & Visual Cell Alignment
# ---------------------------------------------------------

class TestTerminalInputSanitization(BasePyTodoTest):
    def test_ansi_and_control_char_stripping(self):
        nasty_input = "\x1b[31mExploit Title\x1b[0m\x00\x07\x08\x1b[2J"
        clean = sanitize_text(nasty_input)
        self.assertEqual(clean, "Exploit Title")

    def test_wide_and_emoji_detection(self):
        self.assertTrue(is_wide_or_emoji("中"))
        self.assertTrue(is_wide_or_emoji("🚀"))
        self.assertTrue(is_wide_or_emoji("🔥"))
        self.assertTrue(is_wide_or_emoji("✅"))
        self.assertFalse(is_wide_or_emoji("A"))
        self.assertFalse(is_wide_or_emoji("9"))
        self.assertFalse(is_wide_or_emoji("-"))

    def test_visual_width_calculation(self):
        self.assertEqual(get_visual_width("abc"), 3)
        self.assertEqual(get_visual_width("🚀"), 2)
        # With variation selector
        self.assertEqual(get_visual_width("🚀\ufe0f"), 2)
        self.assertEqual(get_visual_width("PyTodo 🚀"), 9)
        # Strips ANSI before counting width
        self.assertEqual(get_visual_width("\x1b[32mOK\x1b[0m"), 2)

    def test_truncate_visual(self):
        s = "Supercalifragilistic"
        truncated = truncate_visual(s, 10, suffix="…")
        self.assertEqual(get_visual_width(truncated), 10)
        self.assertTrue(truncated.endswith("…"))

        # String with wide emojis
        emoji_str = "🚀🚀🚀🚀🚀"
        trunc_emoji = truncate_visual(emoji_str, 6, suffix="…")
        self.assertLessEqual(get_visual_width(trunc_emoji), 6)

    def test_pad_string(self):
        padded_left = pad_string("Hi", 6, align="left")
        self.assertEqual(padded_left, "Hi    ")
        self.assertEqual(get_visual_width(padded_left), 6)

        padded_right = pad_string("Hi", 6, align="right")
        self.assertEqual(padded_right, "    Hi")
        self.assertEqual(get_visual_width(padded_right), 6)


# ---------------------------------------------------------
# 11. Configuration (`config focus.step`)
# ---------------------------------------------------------

class TestConfigCommand(BasePyTodoTest):
    def test_config_display_all(self):
        res = self.run_cmd("config")
        clean = sanitize_text(res)
        self.assertIn("PyTodo Configuration:", clean)
        self.assertIn("focus.step = 5m (300s)", clean)

    def test_config_focus_step_view(self):
        res = self.run_cmd("config focus.step")
        clean = sanitize_text(res)
        self.assertIn("Current focus timer step: 5m (300s)", clean)

    def test_config_focus_step_update(self):
        res = self.run_cmd("config focus.step 10m")
        clean = sanitize_text(res)
        self.assertIn("Focus timer adjustment step set to: 10m (600s)", clean)
        self.assertEqual(mock_win.PyTodoBridge.getFocusStep(), 600)

        res2 = self.run_cmd("config focus.step 45s")
        clean2 = sanitize_text(res2)
        self.assertIn("Focus timer adjustment step set to: 45s (45s)", clean2)
        self.assertEqual(mock_win.PyTodoBridge.getFocusStep(), 45)

    def test_config_focus_step_boundaries(self):
        # Under minimum (< 10s)
        res_low = self.run_cmd("config focus.step 5s")
        self.assertIn("Error: Minimum focus step is 10s", sanitize_text(res_low))

        # Over maximum (> 120m / 7200s)
        res_high = self.run_cmd("config focus.step 3h")
        self.assertIn("Error: Maximum focus step is 120m", sanitize_text(res_high))

        # Invalid format
        res_inv = self.run_cmd("config focus.step invalid")
        self.assertIn("Error: Invalid duration", sanitize_text(res_inv))

    def test_config_unknown_key(self):
        res = self.run_cmd("config unknown.key 123")
        self.assertIn("Error: Unknown config key 'unknown.key'", sanitize_text(res))


# ---------------------------------------------------------
# 12. Tab Autocompletions
# ---------------------------------------------------------

class TestTabAutocompletions(BasePyTodoTest):
    def test_empty_line_returns_all_verbs(self):
        suggs = json.loads(get_autocomplete_suggestions(""))
        self.assertIn("add", suggs)
        self.assertIn("ls", suggs)
        self.assertIn("done", suggs)
        self.assertIn("undone", suggs)
        self.assertIn("focus", suggs)
        self.assertIn("edit", suggs)
        self.assertIn("link", suggs)

    def test_prefix_verbs_completion(self):
        suggs = json.loads(get_autocomplete_suggestions("ad"))
        self.assertEqual(suggs, ["add", "add-sub"])

        suggs_d = json.loads(get_autocomplete_suggestions("d"))
        self.assertIn("done", suggs_d)
        self.assertIn("delete", suggs_d)

    def test_config_keys_completion(self):
        suggs1 = json.loads(get_autocomplete_suggestions("config "))
        self.assertEqual(suggs1, ["focus.step"])

        suggs2 = json.loads(get_autocomplete_suggestions("config foc"))
        self.assertEqual(suggs2, ["focus.step"])

    def test_task_and_subtask_id_completion(self):
        self.run_cmd('add "Task 1" -s "Sub A" -s "Sub B"')
        self.run_cmd('add "Task 2"')

        # Suggestions for 'done ' trailing space
        suggs = json.loads(get_autocomplete_suggestions("done "))
        self.assertEqual(suggs, ["1", "1.1", "1.2", "2"])

        # Filter by prefix '1.'
        suggs_sub = json.loads(get_autocomplete_suggestions("done 1."))
        self.assertEqual(suggs_sub, ["1.1", "1.2"])

        # For 'edit '
        suggs_edit = json.loads(get_autocomplete_suggestions("edit 2"))
        self.assertEqual(suggs_edit, ["2"])

        # For 'focus ' includes 'step' candidate
        suggs_focus = json.loads(get_autocomplete_suggestions("focus "))
        self.assertEqual(suggs_focus, ["step", "1", "1.1", "1.2", "2"])

        suggs_focus_st = json.loads(get_autocomplete_suggestions("focus st"))
        self.assertEqual(suggs_focus_st, ["step"])


if __name__ == "__main__":
    unittest.main()
