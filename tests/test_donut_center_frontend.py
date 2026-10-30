"""Behavioral checks for accessible, untrusted donut-center captions."""
from html.parser import HTMLParser
from pathlib import Path
import json
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]


class _Elements(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.elements = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def test_full_center_caption_remains_accessible_and_cannot_inject_markup():
    source = (ROOT / "web/app.js").read_text()
    functions = []
    for name in ("esc", "renderDonut"):
        start = re.search(rf"^function {name}\(", source, re.M).start()
        end = re.search(r"^}", source[start:], re.M).end()
        functions.append(source[start:start + end])
    caption = 'Long caption <img src=x onerror="alert(1)"> & "quoted" currency'
    script = """
const state={language:'en',baseCurrency:'USD'};
const optionLabel=value=>value;
const currencyDisplayLabel=value=>value;
const colorAt=()=> '#21a7ff';
const money=value=>String(value);
""" + "\n".join(functions) + "\nconsole.log(JSON.stringify(renderDonut([], 'Allocation', '54%', 100, [" + json.dumps(caption) + "])));"
    result = subprocess.run(["node"], input=script, text=True, capture_output=True, timeout=10, check=True)
    markup = json.loads(result.stdout)
    parsed = _Elements()
    parsed.feed(markup)
    image = next(attrs for tag, attrs in parsed.elements if tag == "svg")
    assert image["role"] == "img"
    assert image["aria-label"] == f"Allocation · 54% · {caption}"
    assert any(attrs.get("title") == caption for _, attrs in parsed.elements)
    assert not any(tag in {"img", "script"} for tag, _ in parsed.elements)
    assert not any(name.startswith("on") for _, attrs in parsed.elements for name in attrs)
