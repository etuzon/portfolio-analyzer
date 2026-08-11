from html.parser import HTMLParser
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


class _VisibleEnglishParser(HTMLParser):
    translated_attributes = {"placeholder", "aria-label", "title", "alt"}

    def __init__(self):
        super().__init__()
        self.skip_depth = 0
        self.values = set()

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip_depth += 1
        for name, value in attrs:
            if name in self.translated_attributes and value and re.search(r"[A-Za-z]", value):
                self.values.add(value.strip())

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data):
        if self.skip_depth:
            return
        value = " ".join(data.split())
        if value and re.search(r"[A-Za-z]", value):
            self.values.add(value)


TECHNICAL_UI_VALUES = {
    "1M", "6M", "1Y", "3Y", "5Y",
    "MA 7", "MA 10", "MA 15", "MA 30",
    "AMEX", "NASDAQ", "NYSE", "TASE", "US", "RSU",
    "ANET, HPE, JNPR", "AVGO, MSFT", "NASDAQ, NYSE, TASE…",
    "USD/ILS, IXIC, GCUSD", "Asia/Jerusalem", "dd/mm/yyyy",
}


def test_hebrew_is_the_default_document_language_and_direction():
    html = (ROOT / "web/index.html").read_text()
    script = (ROOT / "web/app.js").read_text()

    assert '<html lang="he" dir="rtl">' in html
    assert html.index('/i18n.js?v=1.0.1') < html.index('/app.js?v=0.4.84')
    assert 'language: "he"' in script
    assert 'state.language = saved === "en" ? "en" : "he"' in script
    assert 'window.PortfolioI18n?.applyToDocument(state.language)' in script


def test_localization_runtime_handles_dynamic_text_and_attributes():
    i18n = (ROOT / "web/i18n.js").read_text()

    assert '"Portfolio Analyzer": "מנהל תיק השקעות"' in i18n
    assert '"Employee Stock Options": "אופציות לעובדים"' in i18n
    assert '"placeholder", "aria-label", "title", "alt"' in i18n
    assert "new MutationObserver" in i18n
    assert 'field.setAttribute("dir", "auto")' in i18n
    assert 'field.setAttribute("dir", "ltr")' in i18n


def test_rtl_layout_uses_semantic_direction_and_logical_properties():
    styles = (ROOT / "web/styles.css").read_text()

    assert 'html[dir="rtl"] .app-shell' in styles
    assert 'font-family: "Noto Sans Hebrew", Inter' in styles
    assert "border-inline-end: 1px solid #24262b" in styles
    assert "margin-inline-start: auto" in styles
    assert "padding-inline-start: 22px" in styles
    assert "inset-inline-start: 8px" in styles


def test_every_static_english_label_is_translated_or_intentionally_technical():
    html = (ROOT / "web/index.html").read_text()
    i18n = (ROOT / "web/i18n.js").read_text()
    parser = _VisibleEnglishParser()
    parser.feed(html)
    encoded_keys = re.findall(r'^\s+"((?:[^"\\]|\\.)+)":', i18n, re.MULTILINE)
    translation_keys = {json.loads(f'"{key}"') for key in encoded_keys}

    uncovered = parser.values - translation_keys - TECHNICAL_UI_VALUES

    assert uncovered == set()
