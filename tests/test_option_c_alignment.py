import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.stdout.reconfigure(encoding='utf-8')

class MockStorage:
    def __init__(self):
        self.store = {}
    def getItem(self, k):
        return self.store.get(k)
    def setItem(self, k, v):
        self.store[k] = str(v)
    def removeItem(self, k):
        self.store.pop(k, None)

# Mock the Pyodide/browser JS environment
class MockWindow:
    def __init__(self, cols=100):
        self._cols = cols
        self.term = type("Term", (), {"cols": cols})()
        self.PyTodoBridge = type("Bridge", (), {
            "getTerminalCols": lambda: self._cols,
            "triggerBackgroundSync": lambda: None,
            "getLocalISODate": lambda: "2026-09-19"
        })()
        self.Date = type("Date", (), {
            "now": lambda: 1700000000000,
            "new": lambda: type("DateObj", (), {"getTimezoneOffset": lambda: 0})()
        })()
        self.localStorage = MockStorage()

# Inject into sys.modules
mock_win = MockWindow(100)
import types
js_mock = types.ModuleType("js")
js_mock.window = mock_win
js_mock.supabaseClient = None
sys.modules["js"] = js_mock

import main

def test_visual_width_and_emojis():
    # Emojis should evaluate to 2 visual cells
    assert main.get_visual_width("🚀") == 2, f"Expected 2 for rocket, got {main.get_visual_width('🚀')}"
    assert main.get_visual_width("🔥") == 2
    assert main.get_visual_width("✨") == 2
    assert main.get_visual_width("Deploy") == 6
    assert main.get_visual_width("🚀 Deploy") == 9  # 2 + 1 + 6 = 9
    print("[PASS] test_visual_width_and_emojis")

def test_truncate_visual():
    raw = "This is a very long subtask title that should be truncated safely"
    truncated = main.truncate_visual(raw, 20)
    assert main.get_visual_width(truncated) <= 20
    assert truncated.endswith("…")
    print(f"[PASS] test_truncate_visual -> {truncated}")

def test_option_c_alignment_wide():
    mock_win._cols = 100
    sample_todos = [
        {
            "id": "1",
            "uuid": "u1",
            "title": "Ship Production Build",
            "done": False,
            "created_at": "2026-09-19T00:00:00Z",
            "subtasks": [
                {"id": "1.1", "title": "Verify Edge CDN", "done": True},
                {"id": "1.2", "title": "Run integration tests", "done": False}
            ]
        }
    ]
    main.save_local_todos(sample_todos)
    output = main.cli_ls([])
    lines = output.split("\n")
    for i, l in enumerate(lines):
        print(f"Line {i}: {repr(l)}")
    
    header = lines[1]
    clean_header = main.ANSI_ESCAPE_RE.sub('', header)
    task_idx = clean_header.index("TASK")
    assert task_idx == 43, f"Expected TASK column at index 43, got {task_idx}"
    
    # Check subtask lines (line 0 is progress, line 1 is header, line 2 is separator, line 3 is parent task, line 4 is subtask 1, line 5 is subtask 2)
    clean_sub1 = main.ANSI_ESCAPE_RE.sub('', lines[4])
    clean_sub2 = main.ANSI_ESCAPE_RE.sub('', lines[5])
    
    # Leading spaces on subtask line should be 49
    leading_spaces = len(clean_sub1) - len(clean_sub1.lstrip(' '))
    assert leading_spaces == 49, f"Expected 49 leading spaces, got {leading_spaces}"
    
    # Subtask tree branch starts at col 49
    assert clean_sub1[49:53] == "├── ", f"Expected '├── ' at index 49, got '{clean_sub1[49:53]}'"
    assert clean_sub2[49:53] == "└── ", f"Expected '└── ' at index 49, got '{clean_sub2[49:53]}'"
    
    # Checkbox glyph: [✓] or [○]
    assert clean_sub1[53:57] == "[✓] ", f"Expected '[✓] ' at index 53, got '{clean_sub1[53:57]}'"
    assert clean_sub2[53:57] == "[○] ", f"Expected '[○] ' at index 53, got '{clean_sub2[53:57]}'"
    
    # Subtask ID
    assert clean_sub1[57:62] == "1.1  ", f"Expected '1.1  ' at index 57, got '{clean_sub1[57:62]}'"
    
    # Subtask title
    assert clean_sub1[62:] == "Verify Edge CDN", f"Expected 'Verify Edge CDN' at index 62, got '{clean_sub1[62:]}'"
    
    # ANSI escape code hygiene: completed subtask should have strikethrough \x1b[9m and explicit \x1b[29m\x1b[0m
    raw_sub1 = lines[4]
    assert "\x1b[9m" in raw_sub1
    assert "\x1b[29m\x1b[0m" in raw_sub1
    
    print("[PASS] test_option_c_alignment_wide:")
    for line in lines:
        print("  " + repr(line))

def test_option_c_alignment_compact():
    mock_win._cols = 85
    mock_win.term.cols = 85
    w = main.get_terminal_width()
    print(f"DEBUG: get_terminal_width() returned {w}")
    output = main.cli_ls([])
    lines = output.split("\n")
    clean_sub1 = main.ANSI_ESCAPE_RE.sub('', lines[4])
    leading_spaces = len(clean_sub1) - len(clean_sub1.lstrip(' '))
    assert leading_spaces == 43, f"Expected 43 leading spaces for compact, got {leading_spaces}"
    print(f"[PASS] test_option_c_alignment_compact (leading_spaces = {leading_spaces})")

def test_dashboard_frame_subtasks():
    mock_win._cols = 100
    frame = main.get_dashboard_frame()
    clean_frame = main.ANSI_ESCAPE_RE.sub('', frame)
    assert "Ship Production Build" in clean_frame
    assert "[1/2 done]" in clean_frame
    assert "├── [✓] 1.1  Verify Edge CDN" in clean_frame
    assert "└── [○] 1.2  Run integration tests" in clean_frame
    print("[PASS] test_dashboard_frame_subtasks")

if __name__ == "__main__":
    test_visual_width_and_emojis()
    test_truncate_visual()
    test_option_c_alignment_wide()
    test_option_c_alignment_compact()
    test_dashboard_frame_subtasks()
    print("\nALL INVARIANT TESTS PASSED PERFECTLY!")
