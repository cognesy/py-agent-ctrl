from __future__ import annotations

from dataclasses import dataclass, field

from py_agent_ctrl.api.events import AgentToolCallEvent
from py_agent_ctrl.api.models import ToolCall, ToolCallPhase, infer_tool_call_phase


@dataclass(slots=True)
class ToolCallLifecycleTracker:
    _calls: dict[str, ToolCall] = field(default_factory=dict)
    _order: list[str] = field(default_factory=list)

    def apply_event(self, event: AgentToolCallEvent) -> ToolCall:
        return self.apply_tool_call(event.tool_call, phase=event.phase)

    def apply_tool_call(self, tool_call: ToolCall, *, phase: ToolCallPhase | None = None) -> ToolCall:
        next_phase = phase or tool_call.phase or infer_tool_call_phase(tool_call.status)
        next_call = tool_call.model_copy(update={"phase": next_phase})
        key = self._key_for(next_call)
        existing = self._calls.get(key)
        if existing is None:
            self._calls[key] = next_call
            self._order.append(key)
            return next_call
        merged = _merge_tool_calls(existing, next_call)
        self._calls[key] = merged
        return merged

    def snapshots(self) -> list[ToolCall]:
        return [self._calls[key] for key in self._order]

    def _key_for(self, tool_call: ToolCall) -> str:
        if tool_call.id:
            return f"id:{tool_call.id}"
        key = f"generated:{len(self._order)}:{tool_call.name}"
        return key


def _merge_tool_calls(existing: ToolCall, incoming: ToolCall) -> ToolCall:
    arguments = incoming.arguments or existing.arguments
    return existing.model_copy(
        update={
            "name": incoming.name or existing.name,
            "kind": incoming.kind or existing.kind,
            "arguments": arguments,
            "output": incoming.output if incoming.output is not None else existing.output,
            "is_error": incoming.is_error or existing.is_error,
            "status": incoming.status or existing.status,
            "phase": incoming.phase or existing.phase,
            "raw": incoming.raw or existing.raw,
        }
    )
