from app.llm_assistant import AssistantError, PortfolioAssistant, assistant_settings


CATALOG = {
    "get_report": {
        "path": "/api/local/reports",
        "description": "Read a report.",
        "parameters": {"type": "object", "properties": {}},
    },
}


def _settings(**values):
    return assistant_settings({"llm": {"enabled": True, "base_url": "https://llm.example/v1", "api_key": "test-key", "model": "test-model", **values}})


def test_assistant_executes_only_catalogued_read_tool_then_answers():
    responses = iter([
        {"choices": [{"message": {"role": "assistant", "tool_calls": [{"id": "call-1", "function": {"name": "get_report", "arguments": "{}"}}]}}]},
        {"choices": [{"message": {"role": "assistant", "content": "Your report is ready."}}]},
    ])
    assistant = PortfolioAssistant(_settings(), CATALOG, caller=lambda **_kwargs: next(responses))
    result = assistant.ask("How am I doing?", "en", lambda name, args: {"name": name, "args": args})

    assert result["answer"] == "Your report is ready."
    assert result["tool_calls"] == [{"tool": "get_report", "path": "/api/local/reports", "arguments": {}}]


def test_assistant_rejects_tool_outside_allow_list():
    assistant = PortfolioAssistant(
        _settings(), CATALOG,
        caller=lambda **_kwargs: {"choices": [{"message": {"role": "assistant", "tool_calls": [{"id": "bad", "function": {"name": "delete_everything", "arguments": "{}"}}]}}]},
    )

    try:
        assistant.ask("Delete data", "en", lambda _name, _args: {})
    except AssistantError as exc:
        assert "configured 6-step" in str(exc)
    else:
        raise AssertionError("the assistant must not execute a non-catalog tool")


def test_assistant_caps_each_question_at_configured_tool_loop_limit():
    assistant = PortfolioAssistant(
        _settings(max_tool_loops=2), CATALOG,
        caller=lambda **_kwargs: {"choices": [{"message": {"role": "assistant", "tool_calls": [{"id": "again", "function": {"name": "get_report", "arguments": "{}"}}]}}]},
    )

    try:
        assistant.ask("Loop", "en", lambda _name, _args: {})
    except AssistantError as exc:
        assert "configured 2-step" in str(exc)
    else:
        raise AssertionError("the configured loop cap must stop the request")


def test_assistant_includes_saved_user_and_answer_context_before_new_prompt():
    received = []
    assistant = PortfolioAssistant(
        _settings(max_context_messages=2), CATALOG,
        caller=lambda **kwargs: received.append(kwargs["messages"]) or {"choices": [{"message": {"role": "assistant", "content": "Understood."}}]},
    )

    assistant.ask(
        "What about that?", "en", lambda _name, _args: {},
        [{"role": "user", "content": "What is my risk?"}, {"role": "assistant", "content": "It is moderate."}],
    )

    assert received[0][-4:-1] == [
        {"role": "user", "content": "What is my risk?"},
        {"role": "assistant", "content": "It is moderate."},
        {"role": "user", "content": "What about that?"},
    ]
