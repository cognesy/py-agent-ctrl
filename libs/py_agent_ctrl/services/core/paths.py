from __future__ import annotations

from pathlib import Path

from py_agent_ctrl.api.models import AgentRequest
from py_agent_ctrl.services.core.errors import WorkingDirectoryNotFoundError


def normalize_request_paths(request: AgentRequest) -> AgentRequest:
    working_directory = _normalize_working_directory(request.working_directory)
    base = Path(working_directory) if working_directory is not None else Path.cwd()
    additional_directories = [_normalize_path(directory, base=base) for directory in request.additional_directories]
    return request.model_copy(
        update={
            "working_directory": working_directory,
            "additional_directories": additional_directories,
        }
    )


def _normalize_working_directory(path: str | None) -> str | None:
    if path is None:
        return None
    normalized = _normalize_path(path, base=Path.cwd())
    if not Path(normalized).is_dir():
        raise WorkingDirectoryNotFoundError(normalized)
    return normalized


def _normalize_path(path: str, *, base: Path) -> str:
    expanded = Path(path).expanduser()
    if not expanded.is_absolute():
        expanded = base / expanded
    return str(expanded.resolve(strict=False))
