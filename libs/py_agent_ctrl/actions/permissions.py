from __future__ import annotations

from py_agent_ctrl.api.models import PermissionRequest, PermissionResponse


class PermissionBroker:
    def __init__(self) -> None:
        self._pending: dict[str, PermissionRequest] = {}

    def add(self, request: PermissionRequest) -> PermissionRequest:
        self._pending[request.id] = request
        return request

    def pending(self) -> list[PermissionRequest]:
        return list(self._pending.values())

    def get(self, request_id: str) -> PermissionRequest | None:
        return self._pending.get(request_id)

    def resolve(self, request_id: str, response: PermissionResponse) -> PermissionResponse:
        if request_id not in self._pending:
            raise KeyError(request_id)
        del self._pending[request_id]
        return response

    def cancel_all(self) -> dict[str, PermissionResponse]:
        responses = {request_id: PermissionResponse.cancelled() for request_id in self._pending}
        self._pending.clear()
        return responses
