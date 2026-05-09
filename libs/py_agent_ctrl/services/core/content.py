from __future__ import annotations

from py_agent_ctrl.api.models import AgentRequest, ImageContentBlock, content_blocks_to_text


def request_prompt_text(request: AgentRequest) -> str:
    if not request.content:
        return request.prompt
    content_text = content_blocks_to_text(request.content)
    if not request.prompt:
        return content_text
    if not content_text:
        return request.prompt
    return f"{request.prompt}\n\n{content_text}"


def request_image_uris(request: AgentRequest) -> list[str]:
    return [block.uri for block in request.content if isinstance(block, ImageContentBlock) and block.uri]
