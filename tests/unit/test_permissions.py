import pytest
from py_agent_ctrl import (
    AgentType,
    BridgeCapabilities,
    PermissionOption,
    PermissionOptionKind,
    PermissionOutcome,
    PermissionRequest,
    PermissionResponse,
)
from py_agent_ctrl.actions import PermissionBroker
from pydantic import ValidationError


def _request() -> PermissionRequest:
    return PermissionRequest(
        id="perm-1",
        agent_type=AgentType.CODEX,
        execution_id="exec-1",
        session_id="session-1",
        tool_call_id="tool-1",
        tool_name="bash",
        raw_input={"command": "pytest"},
        options=[
            PermissionOption(option_id="allow", name="Allow", kind=PermissionOptionKind.ALLOW_ONCE),
            PermissionOption(option_id="deny", name="Deny", kind=PermissionOptionKind.REJECT_ONCE),
        ],
    )


def test_permission_models_validate_option_kind_and_response_helpers():
    request = _request()
    selected = PermissionResponse.selected("allow")
    cancelled = PermissionResponse.cancelled()

    assert request.options[0].kind == PermissionOptionKind.ALLOW_ONCE
    assert selected.outcome == PermissionOutcome.SELECTED
    assert selected.option_id == "allow"
    assert cancelled.outcome == PermissionOutcome.CANCELLED
    assert cancelled.option_id is None


def test_permission_option_rejects_unknown_kind():
    with pytest.raises(ValidationError):
        PermissionOption(option_id="x", name="X", kind="unknown")


def test_permission_broker_tracks_and_resolves_pending_request():
    broker = PermissionBroker()
    request = broker.add(_request())

    assert broker.get("perm-1") == request
    assert broker.pending() == [request]

    response = broker.resolve("perm-1", PermissionResponse.selected("allow"))

    assert response == PermissionResponse.selected("allow")
    assert broker.pending() == []


def test_permission_broker_rejects_unknown_resolution():
    broker = PermissionBroker()

    with pytest.raises(KeyError):
        broker.resolve("missing", PermissionResponse.cancelled())


def test_permission_broker_cancel_all_clears_pending_requests():
    broker = PermissionBroker()
    broker.add(_request())
    broker.add(_request().model_copy(update={"id": "perm-2", "tool_call_id": "tool-2"}))

    responses = broker.cancel_all()

    assert responses == {
        "perm-1": PermissionResponse.cancelled(),
        "perm-2": PermissionResponse.cancelled(),
    }
    assert broker.pending() == []


def test_bridge_capabilities_default_to_no_permission_support():
    capabilities = BridgeCapabilities(agent_type=AgentType.CODEX, cli_name="codex")

    assert capabilities.supports_permissions is False
