from py_agent_ctrl.api.events import AgentPlanUpdateEvent, AgentReasoningEvent, AgentUsageEvent
from py_agent_ctrl.api.models import AgentRequest, ToolCallPhase, ToolCallStatus, ToolKind
from py_agent_ctrl.services.bridges.codex.command_builder import build_codex_command
from py_agent_ctrl.services.bridges.codex.parser import codex_response_from_output, parse_codex_events
from py_agent_ctrl.services.bridges.gemini.bridge import GeminiBridge
from py_agent_ctrl.services.bridges.gemini.command_builder import build_gemini_command
from py_agent_ctrl.services.bridges.gemini.parser import gemini_response_from_output, parse_gemini_events
from py_agent_ctrl.services.bridges.opencode.bridge import OpenCodeBridge
from py_agent_ctrl.services.bridges.opencode.command_builder import build_opencode_command
from py_agent_ctrl.services.bridges.opencode.parser import opencode_response_from_output, parse_opencode_events
from py_agent_ctrl.services.bridges.pi.bridge import PiBridge
from py_agent_ctrl.services.bridges.pi.command_builder import build_pi_command
from py_agent_ctrl.services.bridges.pi.parser import parse_pi_events, pi_response_from_output


def test_codex_builder_and_parser(monkeypatch):
    monkeypatch.setattr(
        "py_agent_ctrl.services.bridges.codex.command_builder.require_binary",
        lambda *_args, **_kwargs: "/tmp/codex",
    )
    request = AgentRequest(
        prompt="review",
        model="o4-mini",
        working_directory="/tmp/work",
        additional_directories=["/tmp/extra"],
        provider_options={"sandbox": "workspace-write", "full_auto": True},
    )
    argv = build_codex_command(request)
    assert argv[:3] == ["/tmp/codex", "exec", "review"]
    assert argv[argv.index("--sandbox") + 1] == "workspace-write"
    assert "--full-auto" in argv

    raw_events = [
        {"type": "thread.started", "thread_id": "thread_stream"},
        {
            "type": "item.completed",
            "item": {"id": "msg_1", "type": "agent_message", "status": "completed", "text": "Hello from codex"},
        },
        {
            "type": "item.completed",
            "item": {
                "id": "cmd_1",
                "type": "command_execution",
                "status": "completed",
                "command": "echo hi",
                "output": "hi",
                "exit_code": 0,
            },
        },
        {
            "type": "item.completed",
            "item": {"id": "reason_1", "type": "reasoning", "status": "completed", "text": "I should inspect tests."},
        },
        {
            "type": "item.completed",
            "item": {"id": "plan_1", "type": "plan_update", "status": "completed", "plan": [{"step": "Run tests"}]},
        },
        {"type": "turn.completed", "usage": {"input_tokens": 9, "cached_input_tokens": 3, "output_tokens": 2}},
    ]
    events = [event for raw in raw_events for event in parse_codex_events(raw)]
    reasoning_events = [event for event in events if isinstance(event, AgentReasoningEvent)]
    plan_events = [event for event in events if isinstance(event, AgentPlanUpdateEvent)]
    usage_events = [event for event in events if isinstance(event, AgentUsageEvent)]
    response = codex_response_from_output(
        events=events,
        raw_events=raw_events,
        exit_code=0,
        parse_failures=0,
        parse_failure_samples=[],
    )
    assert response.session_id == "thread_stream"
    assert response.text == "Hello from codex"
    assert response.usage.input_tokens == 9
    assert response.usage.cache_read_tokens == 3
    assert response.tool_calls[0].name == "bash"
    assert response.tool_calls[0].kind is ToolKind.EXECUTE
    assert response.tool_calls[0].status is ToolCallStatus.COMPLETED
    assert response.tool_calls[0].phase is ToolCallPhase.COMPLETED
    assert reasoning_events[0].text == "I should inspect tests."
    assert plan_events[0].plan == [{"step": "Run tests"}]
    assert usage_events[0].usage.output_tokens == 2
    assert [tool.name for tool in response.tool_calls] == ["bash", "reasoning", "plan_update"]
    assert [tool.kind for tool in response.tool_calls] == [ToolKind.EXECUTE, ToolKind.THINK, ToolKind.THINK]
    assert [tool.status for tool in response.tool_calls] == [
        ToolCallStatus.COMPLETED,
        ToolCallStatus.COMPLETED,
        ToolCallStatus.COMPLETED,
    ]
    assert [tool.phase for tool in response.tool_calls] == [
        ToolCallPhase.COMPLETED,
        ToolCallPhase.COMPLETED,
        ToolCallPhase.COMPLETED,
    ]


def test_opencode_builder_and_parser(monkeypatch):
    monkeypatch.setattr(
        "py_agent_ctrl.services.bridges.opencode.command_builder.require_binary",
        lambda *_args, **_kwargs: "/tmp/opencode",
    )
    request = AgentRequest(
        prompt="review",
        model="anthropic/claude-sonnet-4-5",
        provider_options={"agent": "coder", "files": ["/tmp/a.py"], "title": "t", "share_session": True},
    )
    argv = build_opencode_command(request)
    assert argv[:4] == ["/tmp/opencode", "run", "--format", "json"]
    assert "--share" in argv
    assert argv[argv.index("--agent") + 1] == "coder"

    raw_events = [
        {
            "type": "step_start",
            "timestamp": 1,
            "sessionID": "sess_stream",
            "part": {"messageID": "msg_1", "id": "part_1", "snapshot": "snap"},
        },
        {
            "type": "text",
            "timestamp": 2,
            "sessionID": "sess_stream",
            "part": {"messageID": "msg_1", "id": "part_2", "text": "Hello OpenCode"},
        },
        {
            "type": "tool_use",
            "timestamp": 3,
            "sessionID": "sess_stream",
            "part": {
                "messageID": "msg_1",
                "id": "part_3",
                "callID": "call_1",
                "tool": "bash",
                "state": {"status": "completed", "input": {"command": "pwd"}, "output": {"cwd": "/tmp"}},
            },
        },
        {
            "type": "step_finish",
            "timestamp": 4,
            "sessionID": "sess_stream",
            "part": {
                "messageID": "msg_1",
                "id": "part_4",
                "cost": 0.42,
                "tokens": {"input": 11, "output": 5, "reasoning": 1, "cache": {"read": 2, "write": 1}},
            },
        },
    ]
    events = [event for raw in raw_events for event in parse_opencode_events(raw)]
    response = opencode_response_from_output(
        events=events,
        raw_events=raw_events,
        exit_code=0,
        parse_failures=0,
        parse_failure_samples=[],
    )
    assert response.session_id == "sess_stream"
    assert response.text == "Hello OpenCode"
    assert response.cost_usd == 0.42
    assert response.usage.reasoning_tokens == 1
    assert response.tool_calls[0].name == "bash"
    assert response.tool_calls[0].kind is ToolKind.EXECUTE
    assert response.tool_calls[0].status is ToolCallStatus.COMPLETED
    assert response.tool_calls[0].phase is ToolCallPhase.COMPLETED


def test_pi_builder_and_parser(monkeypatch):
    monkeypatch.setattr(
        "py_agent_ctrl.services.bridges.pi.command_builder.require_binary",
        lambda *_args, **_kwargs: "/tmp/pi",
    )
    request = AgentRequest(
        prompt="review",
        model="sonnet",
        provider_options={"tools": ["read", "grep"], "thinking": "high", "session_dir": "/tmp/sessions"},
    )
    argv = build_pi_command(request)
    assert argv[:3] == ["/tmp/pi", "--mode", "json"]
    assert argv[argv.index("--thinking") + 1] == "high"
    assert argv[argv.index("--tools") + 1] == "read,grep"

    raw_events = [
        {"type": "session", "version": 3, "id": "pi-session", "cwd": "/tmp", "timestamp": "2025-01-01T00:00:00Z"},
        {"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "delta": "Hello"}, "message": {}},
        {
            "type": "tool_execution_end",
            "toolCallId": "tool-1",
            "toolName": "bash",
            "result": {"ok": True},
            "isError": False,
        },
        {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": " world"}],
                "usage": {
                    "input": 3,
                    "output": 5,
                    "cacheRead": 0,
                    "cacheWrite": 2,
                    "totalTokens": 10,
                    "cost": {"total": 0.12},
                },
            },
        },
    ]
    events = [event for raw in raw_events for event in parse_pi_events(raw)]
    response = pi_response_from_output(
        events=events,
        raw_events=raw_events,
        exit_code=0,
        parse_failures=0,
        parse_failure_samples=[],
    )
    assert response.session_id == "pi-session"
    assert response.text == "Hello world"
    assert response.cost_usd == 0.12
    assert response.usage.total_tokens == 10
    assert response.tool_calls[0].name == "bash"
    assert response.tool_calls[0].kind is ToolKind.EXECUTE
    assert response.tool_calls[0].status is ToolCallStatus.COMPLETED
    assert response.tool_calls[0].phase is ToolCallPhase.COMPLETED


def test_gemini_builder_and_parser(monkeypatch):
    monkeypatch.setattr(
        "py_agent_ctrl.services.bridges.gemini.command_builder.require_binary",
        lambda *_args, **_kwargs: "/tmp/gemini",
    )
    request = AgentRequest(
        prompt="review",
        model="flash",
        provider_options={"approval_mode": "plan", "sandbox": True, "allowed_tools": ["read_file"]},
    )
    argv = build_gemini_command(request)
    assert argv[:3] == ["/tmp/gemini", "--output-format", "stream-json"]
    assert argv[argv.index("--approval-mode") + 1] == "plan"
    assert "--sandbox" in argv

    raw_events = [
        {"type": "init", "session_id": "gemini-session"},
        {"type": "message", "role": "assistant", "content": "Hello", "delta": True},
        {"type": "tool_use", "tool_name": "read_file", "tool_id": "call_1", "parameters": {"path": "README.md"}},
        {"type": "tool_result", "tool_id": "call_1", "status": "success", "output": "contents"},
        {
            "type": "result",
            "status": "success",
            "stats": {"total_tokens": 100, "input_tokens": 40, "output_tokens": 60, "cached": 5},
        },
    ]
    events = [event for raw in raw_events for event in parse_gemini_events(raw)]
    response = gemini_response_from_output(
        events=events,
        raw_events=raw_events,
        exit_code=0,
        parse_failures=0,
        parse_failure_samples=[],
    )
    assert response.session_id == "gemini-session"
    assert response.text == "Hello"
    assert response.usage.cache_read_tokens == 5
    assert response.tool_calls[0].name == "read_file"
    assert response.tool_calls[0].kind is ToolKind.READ
    assert response.tool_calls[0].status is ToolCallStatus.COMPLETED
    assert response.tool_calls[0].phase is ToolCallPhase.COMPLETED


def test_provider_tool_status_normalization():
    codex_failed = parse_codex_events(
        {
            "type": "item.completed",
            "item": {
                "id": "cmd_fail",
                "type": "command_execution",
                "status": "completed",
                "command": "false",
                "output": "boom",
                "exit_code": 1,
            },
        }
    )[0]
    assert codex_failed.tool_call.status is ToolCallStatus.FAILED
    assert codex_failed.tool_call.phase is ToolCallPhase.FAILED
    assert codex_failed.phase is ToolCallPhase.FAILED
    assert codex_failed.tool_call.kind is ToolKind.EXECUTE
    assert codex_failed.tool_call.raw["item"]["status"] == "completed"

    codex_cancelled = parse_codex_events(
        {
            "type": "item.completed",
            "item": {
                "id": "mcp_cancel",
                "type": "mcp_tool_call",
                "tool": "lookup",
                "arguments": {},
                "result": None,
                "status": "cancelled",
            },
        }
    )[0]
    assert codex_cancelled.tool_call.status is ToolCallStatus.CANCELLED
    assert codex_cancelled.tool_call.phase is ToolCallPhase.CANCELLED
    assert codex_cancelled.phase is ToolCallPhase.CANCELLED
    assert codex_cancelled.tool_call.kind is ToolKind.OTHER
    assert codex_cancelled.tool_call.raw["item"]["status"] == "cancelled"

    opencode_unknown = parse_opencode_events(
        {
            "type": "tool_use",
            "part": {
                "callID": "call_unknown",
                "tool": "custom",
                "state": {"status": "provider-specific", "input": {}, "output": None},
            },
        }
    )[0]
    assert opencode_unknown.tool_call.status is None
    assert opencode_unknown.tool_call.phase is ToolCallPhase.SNAPSHOT
    assert opencode_unknown.phase is ToolCallPhase.SNAPSHOT
    assert opencode_unknown.tool_call.kind is ToolKind.OTHER
    assert opencode_unknown.tool_call.raw["part"]["state"]["status"] == "provider-specific"


def test_codex_tool_kind_classification_for_known_item_types():
    samples = [
        (
            {
                "id": "file_1",
                "type": "file_change",
                "status": "completed",
                "path": "README.md",
                "action": "edit",
                "diff": "---",
            },
            ToolKind.EDIT,
        ),
        (
            {
                "id": "search_1",
                "type": "web_search",
                "status": "completed",
                "query": "py-agent-ctrl",
                "results": [],
            },
            ToolKind.SEARCH,
        ),
        (
            {
                "id": "reason_1",
                "type": "reasoning",
                "status": "completed",
                "text": "thinking",
            },
            ToolKind.THINK,
        ),
    ]
    for item, expected_kind in samples:
        event = parse_codex_events({"type": "item.completed", "item": item})[-1]
        assert event.tool_call.kind is expected_kind
        assert event.tool_call.phase is ToolCallPhase.COMPLETED


def test_bridge_capabilities_expose_specific_stream_features():
    for bridge in (OpenCodeBridge(), PiBridge(), GeminiBridge()):
        capabilities = bridge.capabilities()

        assert capabilities.supports_tool_events is True
        assert capabilities.supports_usage is True
        assert capabilities.supports_structured_json_output is True
        assert capabilities.supports_permission_callbacks is False
