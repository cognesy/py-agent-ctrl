"""Tests for ClaudeCodeClient — argv builder and response parsing."""
import json
import pytest

from agent_ctrl import ClaudeCodeClient, AssistantEvent, ResultEvent, SystemInitEvent
from agent_ctrl.client import _events_to_response, _parse_stdout
from agent_ctrl.events import parse_event


# ── argv builder ──────────────────────────────────────────────────────────────

def test_basic_argv_contains_print_flag():
    argv = ClaudeCodeClient()._build_argv("hello")
    assert "-p" in argv
    assert "hello" in argv


def test_argv_always_uses_stream_json():
    argv = ClaudeCodeClient()._build_argv("x")
    assert "--output-format" in argv
    idx = argv.index("--output-format")
    assert argv[idx + 1] == "stream-json"


def test_argv_with_max_turns():
    argv = ClaudeCodeClient().with_max_turns(3)._build_argv("x")
    idx = argv.index("--max-turns")
    assert argv[idx + 1] == "3"


def test_argv_with_model():
    argv = ClaudeCodeClient().with_model("claude-haiku-4-5-20251001")._build_argv("x")
    idx = argv.index("--model")
    assert argv[idx + 1] == "claude-haiku-4-5-20251001"


def test_argv_resume_session():
    argv = ClaudeCodeClient().resume("abc-123")._build_argv("x")
    idx = argv.index("--resume")
    assert argv[idx + 1] == "abc-123"


def test_argv_continue_session():
    argv = ClaudeCodeClient().continue_session()._build_argv("x")
    assert "--continue" in argv


def test_continue_and_resume_are_mutually_exclusive():
    # continue takes precedence (mirrors PHP implementation)
    argv = ClaudeCodeClient().continue_session().resume("abc")._build_argv("x")
    assert "--continue" in argv
    assert "--resume" not in argv


def test_argv_system_prompt():
    argv = ClaudeCodeClient().with_system_prompt("Be brief.")._build_argv("x")
    idx = argv.index("--system-prompt")
    assert argv[idx + 1] == "Be brief."


def test_argv_append_system_prompt_not_set_when_system_prompt_present():
    # system_prompt takes precedence over append_system_prompt
    argv = (
        ClaudeCodeClient()
        .with_system_prompt("Full.")
        .append_system_prompt("Appended.")
        ._build_argv("x")
    )
    assert "--system-prompt" in argv
    assert "--append-system-prompt" not in argv


def test_argv_permission_mode_default_omitted():
    # "default" mode should NOT emit --permission-mode flag
    argv = ClaudeCodeClient().with_permission_mode("default")._build_argv("x")
    assert "--permission-mode" not in argv


def test_argv_bypass_permissions():
    argv = ClaudeCodeClient()._build_argv("x")  # default is bypassPermissions
    idx = argv.index("--permission-mode")
    assert argv[idx + 1] == "bypassPermissions"


def test_argv_allowed_tools():
    argv = ClaudeCodeClient().with_allowed_tools("Read", "Edit")._build_argv("x")
    idx = argv.index("--allowedTools")
    assert argv[idx + 1] == "Read,Edit"


def test_argv_add_dirs():
    argv = ClaudeCodeClient().with_add_dirs("/tmp/a", "/tmp/b")._build_argv("x")
    add_dir_positions = [i for i, v in enumerate(argv) if v == "--add-dir"]
    assert len(add_dir_positions) == 2


# ── event parsing ─────────────────────────────────────────────────────────────

def test_parse_system_init():
    raw = {"type": "system", "subtype": "init", "session_id": "s123", "tools": ["Read", "Edit"]}
    event = parse_event(raw)
    assert isinstance(event, SystemInitEvent)
    assert event.session_id == "s123"
    assert "Read" in event.tools


def test_parse_system_init_tools_as_dicts():
    raw = {"type": "system", "subtype": "init", "session_id": "s1",
           "tools": [{"name": "Read"}, {"name": "Edit"}]}
    event = parse_event(raw)
    assert isinstance(event, SystemInitEvent)
    assert event.tools == ["Read", "Edit"]


def test_parse_assistant_text():
    raw = {
        "type": "assistant",
        "message": {"role": "assistant", "content": [{"type": "text", "text": "pong"}]},
    }
    event = parse_event(raw)
    assert isinstance(event, AssistantEvent)
    assert event.text == "pong"


def test_parse_result_success():
    raw = {
        "type": "result", "subtype": "success",
        "session_id": "s1", "result": "Done.", "is_error": False,
        "cost_usd": 0.001, "duration_ms": 1500,
    }
    event = parse_event(raw)
    assert isinstance(event, ResultEvent)
    assert event.success is True
    assert event.cost_usd == pytest.approx(0.001)


# ── response assembly ─────────────────────────────────────────────────────────

SAMPLE_STREAM = [
    '{"type":"system","subtype":"init","session_id":"abc","tools":[]}',
    '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"pong"}]}}',
    '{"type":"result","subtype":"success","session_id":"abc","result":"pong","is_error":false,"cost_usd":null,"duration_ms":800}',
]


def test_parse_stdout_extracts_text():
    stdout = "\n".join(SAMPLE_STREAM)
    response = _parse_stdout(stdout, exit_code=0)
    assert response.text == "pong"
    assert response.session_id == "abc"
    assert response.success is True


def test_parse_stdout_handles_empty():
    response = _parse_stdout("", exit_code=0)
    assert response.text == ""
    assert response.session_id is None


def test_parse_stdout_handles_non_json_lines():
    stdout = "some startup noise\n" + "\n".join(SAMPLE_STREAM)
    response = _parse_stdout(stdout, exit_code=0)
    assert response.text == "pong"
