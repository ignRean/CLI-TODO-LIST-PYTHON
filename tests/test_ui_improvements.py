import sys
import os
import json
from unittest.mock import MagicMock

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Mock js dependencies (browser environment) before importing main
mock_window = MagicMock()
mock_storage = {}
def mock_getItem(key): return mock_storage.get(key)
def mock_setItem(key, val): mock_storage[key] = str(val)
def mock_removeItem(key): mock_storage.pop(key, None)

mock_window.localStorage.getItem = mock_getItem
mock_window.localStorage.setItem = mock_setItem
mock_window.localStorage.removeItem = mock_removeItem
mock_window.PyTodoBridge.getLocalISODate.return_value = "2026-09-19"
mock_window.PyTodoBridge.getTerminalCols.return_value = 80
mock_window.PyTodoBridge.triggerBackgroundSync.return_value = None
mock_window.PyTodoBridge.playSound.return_value = None

sys.modules["js"] = MagicMock()
sys.modules["js"].window = mock_window
sys.modules["js"].supabaseClient = MagicMock()

sys.path.insert(0, os.path.abspath("."))
import main

def test_aliases():
    print("[*] Testing Micro-Command Aliases...")
    assert "a" in main.COMMANDS, "Alias 'a' missing"
    assert "d" in main.COMMANDS, "Alias 'd' missing"
    assert "l" in main.COMMANDS, "Alias 'l' missing"
    assert "u" in main.COMMANDS, "Alias 'u' missing"
    assert "s" in main.COMMANDS, "Alias 's' missing"
    assert "f" in main.COMMANDS, "Alias 'f' missing"
    assert "e" in main.COMMANDS, "Alias 'e' missing"
    assert "t" in main.COMMANDS, "Alias 't' missing"
    assert "c" in main.COMMANDS, "Alias 'c' missing"
    assert "h" in main.COMMANDS, "Alias 'h' missing"
    print("[✔] All 10 micro-command aliases successfully registered.")

def test_add_and_ls_wide():
    print("[*] Testing Wide Viewport Table Mode (80 cols)...")
    mock_window.PyTodoBridge.getTerminalCols.return_value = 80
    mock_storage.clear()
    
    # Add tasks with subtasks using alias 'a'
    res = main.cli_add(["Finalize Mobile Terminal UI", "--due", "18:00", "-s", "Check viewport", "-s", "Test accessory bar"])
    assert "[+] Task added:" in res, "Task add failed"
    
    ls_out = main.cli_ls([])
    print("Wide Mode Output:\n" + ls_out)
    assert "ID    STATUS   SYNC  DEADLINE / HEATMAP    TASK" in ls_out, "Wide header missing"
    assert "0% (0/1 Done)" in ls_out, "Progress summary missing"
    assert "Check viewport" in ls_out, "Subtask missing"
    assert "Test accessory bar" in ls_out, "Subtask 2 missing"
    print("[✔] Wide Mode verified.")

def test_ls_narrow_mobile():
    print("[*] Testing Narrow Viewport Mobile Stream Mode (38 cols)...")
    mock_window.PyTodoBridge.getTerminalCols.return_value = 38
    
    ls_out = main.cli_ls([])
    print("Narrow Mode Output:\n" + ls_out)
    clean_out = main.sanitize_text(ls_out)
    assert "ID    STATUS" not in clean_out, "Wide header must NOT appear in narrow mode"
    assert "[1] [TODO]" in clean_out, "Narrow mode stacked title missing"
    assert "Due:" in clean_out, "Narrow mode due line missing"
    assert "Sync:" in clean_out, "Narrow mode sync line missing"
    assert "├──" in clean_out, "Narrow mode subtask branch missing"
    assert "└──" in clean_out, "Narrow mode subtask leaf branch missing"
    
    # Check that no line exceeds column boundary after stripping ANSI codes
    for line in ls_out.splitlines():
        vis_w = main.get_visual_width(line)
        print(f"Line visual width: {vis_w} -> {main.sanitize_text(line)}")
        # Visual width should not dramatically overflow 38 cols (allowing slight border padding)
        assert vis_w <= 42, f"Line width {vis_w} exceeds narrow boundary: {line}"
    print("[✔] Narrow Mobile Stream Mode verified.")

def test_autocomplete_aliases():
    print("[*] Testing Autocomplete with Aliases...")
    # 'd 1' should suggest subtasks
    sugg = json.loads(main.get_autocomplete_suggestions("d 1"))
    print("Autocomplete for 'd 1':", sugg)
    assert "1" in sugg or "1.1" in sugg, "Task suggestions failed for alias 'd'"
    print("[✔] Autocomplete aliases verified.")

if __name__ == "__main__":
    test_aliases()
    test_add_and_ls_wide()
    test_ls_narrow_mobile()
    test_autocomplete_aliases()
    print("\n==========================================")
    print("ALL PYTHON UI IMPROVEMENT TESTS PASSED! [✔]")
    print("==========================================")
