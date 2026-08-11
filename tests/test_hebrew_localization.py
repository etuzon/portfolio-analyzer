from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_hebrew_is_the_default_document_language_and_direction():
    html = (ROOT / "web/index.html").read_text()
    script = (ROOT / "web/app.js").read_text()

    assert '<html lang="he" dir="rtl">' in html
    assert html.index('/i18n.js?v=0.1.0') < html.index('/app.js?v=0.4.84')
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
