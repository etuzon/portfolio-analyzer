import json

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


def test_assistant_receives_event_workflow_before_answering_without_evidence():
    from app import main

    messages_seen = []
    responses = iter([
        {"choices": [{"message": {"role": "assistant", "tool_calls": [{"id": "workflow", "function": {"name": "get_event_impact_workflow", "arguments": "{}"}}]}}]},
        {"choices": [{"message": {"role": "assistant", "content": "Unknown: no verified comparable cases were supplied."}}]},
    ])

    def provider(**kwargs):
        messages_seen.append(list(kwargs["messages"]))
        return next(responses)

    assistant = PortfolioAssistant(_settings(), main.ASSISTANT_READ_TOOLS, caller=provider)
    result = assistant.ask("How likely is a stock loss after this event?", "en", lambda _name, _args: main.event_impact_workflow())
    received = json.loads(messages_seen[-1][-1]["content"])
    assert received["workflow_id"] == "world-event-impact"
    assert set(received["probability_definitions"]) >= {
        "event", "exposure", "direction", "severity", "onset", "persistence",
        "recovery", "spillover", "scenario", "joint_loss",
    }
    assert received["templates"]["probability"]["estimate_pct"] is None
    assert received["capabilities"]["trained_probability_model"] is False
    assert "Unknown" in result["answer"]
    # This verifies tool delivery, not the forecasting reliability of an external LLM.


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


def test_disabling_context_does_not_send_saved_messages():
    received = []
    assistant = PortfolioAssistant(
        _settings(max_context_messages=0), CATALOG,
        caller=lambda **kwargs: received.append(list(kwargs["messages"])) or {"choices": [{"message": {"role": "assistant", "content": "Unknown."}}]},
    )
    assistant.ask("New question", "en", lambda *_args: {}, [{"role": "user", "content": "Old private context"}])
    assert [message["role"] for message in received[0]] == ["system", "user"]
    assert "Old private context" not in json.dumps(received)


def test_sixth_exchange_answers_without_more_tools():
    requests = []
    def caller(**kwargs):
        requests.append(kwargs["tools"])
        message = {"role": "assistant", "content": "The available evidence is complete."} if not kwargs["tools"] else {
            "role": "assistant", "tool_calls": [{"id": str(len(requests)), "function": {"name": "get_report", "arguments": "{}"}}],
        }
        return {"choices": [{"message": message}]}
    assistant = PortfolioAssistant(_settings(max_tool_loops=99), CATALOG, caller=caller)
    reads = []
    result = assistant.ask("Read the evidence", "en", lambda name, arguments: reads.append(name) or {"verified": True})
    assert result["model_requests"] == len(requests) == 6
    assert len(reads) == 5
    assert requests[-1] == []
    assert result["answer"] == "The available evidence is complete."
