from py_agent_ctrl.api.events import AgentTextEvent, AgentUnknownEvent, StreamDiagnostics, StreamResult


def _make_result(events, exit_code=0):
    code = [exit_code]
    return StreamResult(iter(events), lambda: code[0])


def test_exit_code_reflects_getter_value():
    result = _make_result([], exit_code=42)
    list(result)
    assert result.exit_code == 42


def test_exit_code_accessible_before_exhaustion():
    result = _make_result([], exit_code=7)
    # getter is called on property access regardless of iteration state
    assert result.exit_code == 7


def test_exit_code_is_zero_for_success():
    result = _make_result([AgentTextEvent(text="hi")], exit_code=0)
    list(result)
    assert result.exit_code == 0


def test_iteration_yields_all_events():
    events = [AgentTextEvent(text="a"), AgentTextEvent(text="b"), AgentUnknownEvent()]
    result = _make_result(events)
    assert [e.type for e in result] == ["text", "text", "unknown"]


def test_second_iteration_yields_nothing():
    result = _make_result([AgentTextEvent(text="once")])
    first = list(result)
    second = list(result)
    assert len(first) == 1
    assert second == []


def test_default_diagnostics_are_empty():
    result = _make_result([])
    list(result)

    assert result.diagnostics == StreamDiagnostics()


def test_diagnostics_reflect_getter_after_exhaustion():
    diagnostics = StreamDiagnostics(
        parse_failures=1,
        skipped_non_json_lines=1,
        parse_failure_samples=["not-json"],
        command_preview=["agent", "run"],
        cwd="/tmp/work",
    )
    result = StreamResult(iter([AgentTextEvent(text="ok")]), lambda: 0, lambda: diagnostics)

    assert [event.type for event in result] == ["text"]
    assert result.diagnostics.parse_failures == 1
    assert result.diagnostics.skipped_non_json_lines == 1
    assert result.diagnostics.parse_failure_samples == ["not-json"]
    assert result.diagnostics.command_preview == ["agent", "run"]
    assert result.diagnostics.cwd == "/tmp/work"
