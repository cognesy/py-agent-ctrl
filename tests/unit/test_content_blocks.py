from py_agent_ctrl import (
    AgentRequest,
    DiffContentBlock,
    EmbeddedResourceContentBlock,
    ImageContentBlock,
    ResourceLinkContentBlock,
    TerminalContentBlock,
    TextContentBlock,
    ToolCall,
    content_blocks_to_text,
    diff_block,
    embedded_blob_resource_block,
    embedded_text_resource_block,
    image_data_block,
    image_ref_block,
    resource_link_block,
    terminal_ref_block,
    text_block,
)


def test_existing_string_prompt_request_still_works():
    request = AgentRequest(prompt="review")

    assert request.prompt == "review"


def test_content_helpers_create_typed_models():
    blocks = [
        text_block("Review this."),
        resource_link_block("file:///tmp/README.md", name="README.md", mime_type="text/markdown"),
        embedded_text_resource_block("memory://note", "remember this"),
        embedded_blob_resource_block("file:///tmp/data.bin", "YWJj", mime_type="application/octet-stream"),
        image_ref_block("/tmp/screenshot.png", mime_type="image/png"),
        image_data_block("iVBORw0KGgo=", mime_type="image/png"),
        diff_block("app.py", "new", "old"),
        terminal_ref_block("term-1", "stdout"),
    ]

    assert isinstance(blocks[0], TextContentBlock)
    assert isinstance(blocks[1], ResourceLinkContentBlock)
    assert isinstance(blocks[2], EmbeddedResourceContentBlock)
    assert isinstance(blocks[3], EmbeddedResourceContentBlock)
    assert isinstance(blocks[4], ImageContentBlock)
    assert isinstance(blocks[5], ImageContentBlock)
    assert isinstance(blocks[6], DiffContentBlock)
    assert isinstance(blocks[7], TerminalContentBlock)


def test_content_blocks_serialize_with_discriminators():
    block = resource_link_block("file:///tmp/README.md", name="README.md", size=123)

    assert block.model_dump() == {
        "type": "resource_link",
        "uri": "file:///tmp/README.md",
        "name": "README.md",
        "mime_type": None,
        "size": 123,
        "description": None,
    }


def test_content_blocks_to_text_is_deterministic():
    text = content_blocks_to_text(
        [
            text_block("Review this."),
            resource_link_block("file:///tmp/README.md", name="README.md"),
            embedded_text_resource_block("memory://note", "remember this"),
            embedded_blob_resource_block("file:///tmp/data.bin", "YWJj", mime_type="application/octet-stream"),
            image_ref_block("/tmp/screenshot.png"),
            image_data_block("iVBORw0KGgo=", mime_type="image/png"),
            diff_block("app.py", "new", "old"),
            terminal_ref_block("term-1", "stdout"),
        ]
    )

    assert text == (
        "Review this.\n\n"
        "[resource: README.md] file:///tmp/README.md\n\n"
        "[resource: memory://note]\n"
        "remember this\n\n"
        "[resource: file:///tmp/data.bin] <application/octet-stream>\n\n"
        "[image: /tmp/screenshot.png]\n\n"
        "[image: <image/png>]\n\n"
        "[diff: app.py]\n"
        "--- old\n"
        "old\n"
        "+++ new\n"
        "new\n\n"
        "[terminal: term-1]\n"
        "stdout"
    )


def test_diff_and_terminal_fallbacks_handle_minimal_blocks():
    assert content_blocks_to_text([diff_block("app.py", "new")]) == "[diff: app.py]\nnew"
    assert content_blocks_to_text([terminal_ref_block("term-1")]) == "[terminal: term-1]"


def test_tool_calls_can_hold_content_blocks_without_replacing_output():
    tool_call = ToolCall(name="bash", output="stdout", content=[text_block("stdout")])

    assert tool_call.output == "stdout"
    assert isinstance(tool_call.content[0], TextContentBlock)
    assert tool_call.content[0].text == "stdout"
