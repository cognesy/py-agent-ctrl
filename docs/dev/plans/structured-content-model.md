# Structured Content Model Plan

bd parent: `bd-1jh.12`

## Goal

Add a typed content model to `py-agent-ctrl` so callers and provider parsers can
represent text, resource links, embedded resources, images, diffs, and terminal
references without turning every rich artifact into provider-specific ad hoc
dicts.

The simple API must remain intact:

- `AgentCtrl.codex().execute("plain text")`
- `AgentCtrl.codex().stream("plain text")`
- `AgentRequest(prompt="plain text")`

Structured content is an additive lower-level contract for advanced callers and
future provider features.

## Non-goals

- Do not implement ACP or expose an ACP wire/runtime contract.
- Do not make provider CLIs accept content they cannot actually consume.
- Do not inline binary files by default.
- Do not replace `AgentTextEvent.text` or `AgentResponse.text`; keep them as
  convenience plain-text views.
- Do not solve the whole file-change/diff event redesign here. Add content
  primitives that the later file-change epic can reuse.

## Research Findings

Current `py-agent-ctrl` state:

- `AgentRequest.prompt` is a required `str`.
- `BaseAgentAction.execute(prompt: str)` and `.stream(prompt: str)` copy the
  string into `AgentRequest.prompt`.
- Claude Code, Codex, Gemini, OpenCode, and Pi command builders all append or
  pass `request.prompt` directly to provider argv.
- Codex already supports images through provider option `images`, lowered as
  repeated `--image` flags.
- OpenCode and Pi support file attachment/reference provider options, but those
  are not part of a common content model.
- Output models are mostly plain text plus `raw`; tool outputs can contain
  arbitrary provider-native values.

ACP SDK reference findings:

- ACP uses content blocks for prompt and stream updates: text, resource link,
  embedded resource, image, and audio.
- ACP tool-call content has separate variants for ordinary content, diff/file
  edits, and terminal references.
- `src/acp/helpers.py` is the useful design reference: small constructor helpers
  such as `text_block`, `resource_link_block`, `image_block`,
  `tool_diff_content`, and `tool_terminal_ref`.
- The SDK keeps capability awareness separate from the content model. Optional
  content types are advertised before clients send them.

Feasibility probe:

- A deterministic text fallback for text/resource/image blocks is trivial and
  compatible with all current command builders.
- Provider-native lowering should be explicit and incremental. The first
  provider-native win is Codex images because the bridge already has `--image`
  support.

## Proposed Model

Add internal Pydantic models under `api/models.py`:

- `TextContentBlock(type="text", text: str)`
- `ResourceLinkContentBlock(type="resource_link", uri: str, name: str | None,
  mime_type: str | None, size: int | None, description: str | None)`
- `EmbeddedResourceContentBlock(type="resource", uri: str, text: str | None,
  blob: str | None, mime_type: str | None)`
- `ImageContentBlock(type="image", uri: str | None, data: str | None,
  mime_type: str | None)`
- `DiffContentBlock(type="diff", path: str, new_text: str,
  old_text: str | None)`
- `TerminalContentBlock(type="terminal", terminal_id: str,
  output: str | None)`

Define unions:

- `PromptContentBlock`: text, resource link, embedded resource, image.
- `OutputContentBlock`: prompt blocks plus diff and terminal.
- `ToolCallContentBlock`: output blocks.

Add helpers:

- `text_block(text)`
- `resource_link(uri, ...)`
- `embedded_text_resource(uri, text, ...)`
- `image_ref(path_or_uri, ...)`
- `diff_block(path, new_text, old_text=None)`
- `terminal_ref(terminal_id, output=None)`
- `content_blocks_to_text(blocks)`

## Request API Strategy

Keep `AgentRequest.prompt: str` as the compatibility field.

Add:

```python
content: list[PromptContentBlock] = Field(default_factory=list)
```

Rules:

- If `content` is empty, providers use `prompt`.
- If `content` is present and `prompt` is empty, providers use the plain-text
  fallback generated from `content`.
- If both are present, providers use `prompt` followed by the plain-text fallback
  for non-text blocks. This avoids dropping explicit caller text.
- Provider-native lowering can consume selected block types while still
  retaining a plain-text fallback for unsupported providers.

Add action helpers without changing `execute(prompt: str)`:

- `with_content(blocks: list[PromptContentBlock])`
- `with_resource(uri, ...)`
- `with_image(path_or_uri, ...)`

## Provider Migration Strategy

Phase 1, safe compatibility:

- Add models and helpers.
- Add `request_prompt_text(request)` helper used by command builders.
- Migrate all command builders from `request.prompt` to the helper.
- Ensure string prompt commands are byte-for-byte unchanged when no content
  blocks are present.

Phase 2, provider-native lowering:

- Codex: lower image reference blocks into `provider_options["images"]` or a
  bridge helper that emits `--image`.
- OpenCode/Pi: consider resource link/file blocks for existing `--file` or
  `@file` provider options only when the URI is a local file path.
- Claude/Gemini: keep text fallback until provider-native content support is
  researched per CLI.

Phase 3, output content:

- Add optional `content` fields to `AgentTextEvent`, `AgentResponse`, and
  `ToolCall`.
- Populate simple text blocks first, preserving `.text`.
- Let later file-change and terminal epics reuse `DiffContentBlock` and
  `TerminalContentBlock`.

## Compatibility Constraints

- Existing imports and constructors must keep working.
- Existing action callbacks receive the same text/tool-call surfaces unless they
  opt into content fields.
- Existing fixture responses must remain text-compatible.
- Unknown or unsupported content must fail early with a clear validation error
  only when it cannot be safely represented as text.

## Risks

- Provider CLIs differ sharply in native rich-input support.
- URI semantics can become ambiguous. The first implementation should accept
  local paths and explicit URI strings but avoid dereferencing remote resources.
- Base64 blobs can create large argv payloads. Do not inline blobs into command
  args by default.
- If `prompt` and `content` are both present, duplicated text is possible unless
  helper rules are clear and tested.

## Open Questions

- Should `execute(...)` later accept `str | list[PromptContentBlock]`, or should
  rich execution require `AgentRequest`/builder methods?
- Should image blocks support raw base64 in the first implementation, or only
  file/URI references?
- Should output content fields be added in the same release as input content, or
  as a separate migration after request lowering is stable?

## Task Breakdown

1. Add content block models and helper functions.
2. Add request content compatibility and plain-text lowering.
3. Migrate command builders to the lowering helper.
4. Add conservative provider-native image/file lowering where already supported.
5. Add optional output content fields for text/tool-call compatibility.
6. Document structured content and provider limitations.

## Verification Plan

- Unit tests for every content block model and helper.
- Command-builder tests proving existing string prompts are unchanged.
- Command-builder tests proving content blocks lower to deterministic text.
- Provider-specific tests for Codex image blocks.
- Mypy and ruff over `libs/py_agent_ctrl`, `apps`, and `tests/unit`.
- ACP wording scan to keep docs framed as inspiration, not runtime support.
