from py_agent_ctrl.api.events import AgentToolCallEvent
from py_agent_ctrl.api.models import ToolCall, ToolCallPhase, ToolCallStatus, ToolKind
from py_agent_ctrl.services.core.tool_calls import ToolCallLifecycleTracker


def test_tracker_records_start_only_tool_call():
    tracker = ToolCallLifecycleTracker()

    tracker.apply_tool_call(
        ToolCall(id="tool-1", name="Read", kind=ToolKind.READ, arguments={"path": "README.md"}, status=ToolCallStatus.PENDING)
    )

    snapshots = tracker.snapshots()
    assert len(snapshots) == 1
    assert snapshots[0].phase is ToolCallPhase.STARTED
    assert snapshots[0].status is ToolCallStatus.PENDING


def test_tracker_records_completed_failed_and_cancelled_snapshots():
    tracker = ToolCallLifecycleTracker()

    tracker.apply_tool_call(ToolCall(id="ok", name="bash", status=ToolCallStatus.COMPLETED))
    tracker.apply_tool_call(ToolCall(id="bad", name="bash", status=ToolCallStatus.FAILED, is_error=True))
    tracker.apply_tool_call(ToolCall(id="cancel", name="lookup", status=ToolCallStatus.CANCELLED))

    snapshots = tracker.snapshots()
    assert [snapshot.phase for snapshot in snapshots] == [
        ToolCallPhase.COMPLETED,
        ToolCallPhase.FAILED,
        ToolCallPhase.CANCELLED,
    ]


def test_tracker_merges_repeated_same_id_updates():
    tracker = ToolCallLifecycleTracker()

    tracker.apply_tool_call(
        ToolCall(id="tool-1", name="bash", arguments={"command": "pwd"}, status=ToolCallStatus.PENDING)
    )
    tracker.apply_tool_call(ToolCall(id="tool-1", name="bash", output="/tmp", status=ToolCallStatus.COMPLETED))

    snapshots = tracker.snapshots()
    assert len(snapshots) == 1
    assert snapshots[0].arguments == {"command": "pwd"}
    assert snapshots[0].output == "/tmp"
    assert snapshots[0].phase is ToolCallPhase.COMPLETED
    assert snapshots[0].status is ToolCallStatus.COMPLETED


def test_tracker_accepts_event_phase_override():
    tracker = ToolCallLifecycleTracker()

    tracker.apply_event(
        AgentToolCallEvent(
            tool_call=ToolCall(id="tool-1", name="custom", status=None),
            phase=ToolCallPhase.UPDATED,
        )
    )

    assert tracker.snapshots()[0].phase is ToolCallPhase.UPDATED
