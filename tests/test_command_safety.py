from app.tools.command_safety import is_safe_argv


def test_allow_python_help():
    ok, reason = is_safe_argv(["python", "demo.py", "--help"], ["demo.py"])
    assert ok


def test_allow_pytest():
    ok, reason = is_safe_argv(["pytest", "-q"], [])
    assert ok


def test_block_unknown_script():
    ok, reason = is_safe_argv(["python", "evil.py", "--help"], ["demo.py"])
    assert not ok


def test_block_shell_metacharacter():
    ok, reason = is_safe_argv(["python", "demo.py;rm", "--help"], ["demo.py"])
    assert not ok


def test_block_parent_path():
    ok, reason = is_safe_argv(["python", "../demo.py", "--help"], ["../demo.py"])
    assert not ok
