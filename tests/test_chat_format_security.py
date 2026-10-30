"""Independent security checks for rich chat text and durable diagnostics."""
import json
from html.parser import HTMLParser
from pathlib import Path
import re
import subprocess

import pytest

from app.diagnostics import Redactor
from app.llm_assistant import PortfolioAssistant
from test_assistant_security import authenticated_chats


@pytest.mark.parametrize("text", [
    "**password:** qa-markdown-private-2026",
    "**password**: qa-markdown-private-2026",
    "__password__: qa-markdown-private-2026",
    "**api_key**: `qa-markdown-private-2026`",
    "| password | qa-markdown-private-2026 |",
    "| Key | Value |\n| --- | --- |\n| password | qa-markdown-private-2026 |",
    "| **password** | `qa-markdown-private-2026` |",
    "| token | qa-markdown-private-2026 | amount | 1234.50 |",
    "**סיסמה:** qa-markdown-private-2026",
    "| סיסמה | qa-markdown-private-2026 |",
])
def test_markdown_credentials_are_redacted_without_configured_secret(text):
    redacted = Redactor().text(text)
    assert "qa-markdown-private-2026" not in redacted
    assert "[REDACTED]" in redacted


@pytest.mark.parametrize("text", [
    ":info[password]: qa-rich-private-2026",
    "| :info[password] | qa-rich-private-2026 |",
    "| Password | Account |\n| --- | --- |\n| qa-rich-private-2026 | QA account |",
    "> | Password | Account |\n> | --- | --- |\n> | qa-rich-private-2026 | QA account |",
])
def test_color_labels_and_sensitive_table_columns_do_not_leak_credentials(text):
    assert "qa-rich-private-2026" not in Redactor().text(text)


@pytest.mark.parametrize("markdown", [
    "**password:** qa-durable-private-2026",
    "| Field | Value |\n| --- | --- |\n| password | qa-durable-private-2026 |",
    ":info[password]: qa-durable-private-2026",
    "| Password | Account |\n| --- | --- |\n| qa-durable-private-2026 | QA account |",
    "> | Password | Account |\n> | --- | --- |\n> | qa-durable-private-2026 | QA account |",
])
def test_formatted_prompt_response_and_followup_context_are_safe_in_durable_logs(authenticated_chats, markdown):
    env = authenticated_chats
    client = env.login()
    def response(*args, **kwargs):
        return {"choices": [{"message": {"role": "assistant", "content": json.dumps({"answer": markdown, "support_status": "answered"})}}]}
    env.patch.setattr(PortfolioAssistant, "_call_provider", response)
    initial = client.post("/api/assistant/questions", json={"prompt": markdown})
    assert initial.status_code == 200, initial.text
    chat_id = initial.json()["chat"]["id"]
    # Saved user/assistant content remains intact. Logging is the redaction boundary.
    assert initial.json()["chat"]["messages"][0]["content"] == markdown
    assert initial.json()["chat"]["messages"][-1]["content"] == markdown
    followup = client.post("/api/assistant/questions", json={"chat_id": chat_id, "prompt": "Read existing chat context"})
    assert followup.status_code == 200
    paths = list((env.store.path.parent / "logs").glob("*.log"))
    assert paths
    logs = "\n".join(path.read_text() for path in paths)
    assert "qa-durable-private-2026" not in logs
    assert "[REDACTED]" in logs
    chat_events = [json.loads(line) for path in paths if path.name == "chat.log" for line in path.read_text().splitlines()]
    assert {event["event"] for event in chat_events} >= {"request_received", "context_loaded", "model_response", "request_completed"}


ROOT = Path(__file__).resolve().parents[1]


def _format_cases(cases, operation="render"):
    script = "const window={};\n" + (ROOT / "web/assistant-format.js").read_text()
    script += "\nconst cases = " + json.dumps(cases, ensure_ascii=True) + ";\n"
    script += "process.stdout.write(JSON.stringify(cases.map(value => window.PortfolioAssistantFormat[" + json.dumps(operation) + "](value))));"
    result = subprocess.run(["node"], input=script, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


class _RenderedHTML(HTMLParser):
    def __init__(self, value):
        super().__init__(convert_charrefs=True)
        self.tags, self.attributes, self.text = [], [], []
        self.feed(value)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attributes.extend(attrs)

    def handle_data(self, value):
        self.text.append(value)


def test_untrusted_rich_text_can_only_produce_safe_fixed_markup():
    attacks = [
        '<img src=x onerror="globalThis.pwned=1"><script>alert(1)</script>',
        '[steal](javascript:alert(1)) ![remote](https://never-used.invalid/a.png)',
        '[x](data:text/html,<svg/onload=alert(1)>) <iframe srcdoc="<script>alert(1)</script>">',
        ':positive[<svg onload=alert(1)>] :red[unsafe] :info[x]" onclick="bad',
        '```html onclick=alert(1)\n</code></pre><script>alert(1)</script>\n```',
        '| Heading | <img src=x> |\n| --- | --- |\n| **unsafe** | <a href="javascript:bad">value</a> |',
        '> <style>body{background:url(https://never-used.invalid)}</style>\n> :warning[**careful**]',
        '# <details open ontoggle=alert(1)>\n- <input autofocus onfocus=alert(1)>',
        ':positive[a [b] c] :negative[bad\\]still] :warning[unclosed',
    ]
    allowed_tags = {"p", "br", "strong", "em", "code", "span", "div", "pre", "h4", "h5", "h6", "table", "caption", "thead", "tbody", "tr", "th", "td", "bdi", "blockquote", "hr", "ul", "ol", "li"}
    allowed_attrs = {"class", "title", "tabindex", "aria-label", "dir", "role", "scope", "start"}
    for rendered in _format_cases(attacks):
        parsed = _RenderedHTML(rendered)
        assert set(parsed.tags) <= allowed_tags
        assert {name for name, _ in parsed.attributes} <= allowed_attrs
        assert not any(name.lower().startswith("on") or name in {"href", "src", "style"} for name, _ in parsed.attributes)
    raw_html = _format_cases([attacks[0]])[0]
    assert attacks[0] in "".join(_RenderedHTML(raw_html).text)


def test_pretty_json_preserves_financial_tokens_and_escaped_strings():
    # Use an independently constructed valid escaped string alongside raw numeric tokens.
    source = '{"total":9007199254740993123456789,"rate":1.234567890123456789,"zero":-0,"exp":1.0200e+30,"label":' + json.dumps('אחוז 12.50% "quoted"\n\\', ensure_ascii=False) + ',"items":[true,null,{},[]]}'
    formatted = _format_cases([source], operation="prettyJson")[0]
    tokens = lambda text: re.findall(r'"(?:\\.|[^"\\])*"|[^\s]', text)
    assert tokens(formatted) == tokens(source)
    assert '\n  "total": 9007199254740993123456789' in formatted
    fenced = _format_cases(["```json\n" + source + "\n```"])[0]
    assert "".join(_RenderedHTML(fenced).text).endswith(formatted)
    invalid = '{"total": 1, <img src=x>}'
    assert _format_cases([invalid], operation="prettyJson")[0] == invalid


def test_tables_keep_escaped_pipes_code_pipes_alignment_rtl_and_all_values():
    source = '| שם | Amount | Change |\n| :--- | ---: | :---: |\n| אלפא \\| בטא | `x|y` | :positive[+12.50%] |\n| חסר | -9007199254740993 | -0.0200 | extra original value |'
    rendered = _format_cases([source])[0]
    parsed = _RenderedHTML(rendered)
    text = "".join(parsed.text)
    for original in ('אלפא | בטא', 'x|y', '+12.50%', '-9007199254740993', '-0.0200', 'extra original value'):
        assert original in text
    assert parsed.tags.count("table") == 1
    assert parsed.tags.count("th") == 4
    assert 'assistant-align-left' in rendered and 'assistant-align-right' in rendered and 'assistant-align-center' in rendered
    assert 'dir="auto"' in rendered


def test_fixed_tones_support_nested_brackets_without_accepting_css_or_execution():
    source = ':positive[gain [12.5%]] :negative[loss] :warning[risk] :info[**facts**] :muted[note] :red[unrecognized] :positive[unclosed'
    rendered = _format_cases([source])[0]
    parsed = _RenderedHTML(rendered)
    classes = [value for name, value in parsed.attributes if name == "class" and value.startswith("assistant-tone ")]
    assert classes == [f"assistant-tone assistant-tone-{tone}" for tone in ("positive", "negative", "warning", "info", "muted")]
    assert 'gain [12.5%]' in "".join(parsed.text)
    assert ':red[unrecognized]' in "".join(parsed.text)
    assert ':positive[unclosed' in "".join(parsed.text)
    assert '<strong>facts</strong>' in rendered


def test_nested_lists_quotes_and_code_preserve_text_without_code_execution():
    source = '# Financial answer\n\n1. Parent\n   - Child **value**\n   - Child *note*\n\n> Quoted :info[context]\n\n```js\nglobalThis.pwned = true;\n:negative[unformatted]\n```'
    rendered = _format_cases([source])[0]
    parsed = _RenderedHTML(rendered)
    assert {'h4', 'ol', 'ul', 'blockquote', 'strong', 'em', 'pre', 'code'} <= set(parsed.tags)
    assert 'globalThis.pwned = true;\n:negative[unformatted]' in ''.join(parsed.text)
    assert 'assistant-tone-negative' not in rendered


def test_extreme_inputs_fall_back_to_escaped_text_without_losing_values():
    deep_json = '[' * 1000 + '900719925474099312345' + ']' * 1000
    assert _format_cases([deep_json], operation="prettyJson")[0] == deep_json
    large_text = '<img src=x onerror=bad>' + 'a' * 200_001 + 'last financial value -123.4500'
    wide_table = '| ' + ' | '.join(f'column {n}' for n in range(40)) + ' |\n| ' + ' | '.join('---' for _ in range(40)) + ' |\n| ' + ' | '.join(f'value-{n}' for n in range(40)) + ' |'
    tall_table = '| Account | Value |\n| --- | --- |\n' + '\n'.join(f'| account-{n} | {n}.000 |' for n in range(550))
    for source, rendered in zip((large_text, wide_table, tall_table), _format_cases([large_text, wide_table, tall_table])):
        parsed = _RenderedHTML(rendered)
        assert set(parsed.tags) <= {"p", "br"}
        # <br> replaces newlines; every original non-newline character survives.
        assert ''.join(parsed.text) == source.replace('\n', '')
