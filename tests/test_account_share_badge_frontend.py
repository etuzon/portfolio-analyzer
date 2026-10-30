"""Focused rendering checks for honest account-share charts and localized text."""
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_share_badge_keeps_actual_values_and_draws_only_valid_percentages():
    source = (ROOT / "web/app.js").read_text()
    functions = []
    for name in ("locale", "esc", "fmt", "optionLabel", "accountShareBadge"):
        start = re.search(rf"^function {name}\(", source, re.M).start()
        end = re.search(r"^}", source[start:], re.M).end()
        functions.append(source[start:start + end])
    script = "\n".join([
        "const assert = require('node:assert/strict');",
        "const window = {}; const OPTION_LABELS = {}; const state = {};",
        (ROOT / "web/i18n.js").read_text(),
        *functions,
        r'''
for (const language of ['en', 'he']) {
  state.language = language;
  const label = language === 'he' ? 'אחוז מסה"כ החשבונות' : 'Share of total accounts';
  for (const [share, dash] of [[46.2, '46.2 53.8'], [0, '0 100'], [100, '100 0']]) {
    const html = accountShareBadge(share);
    assert.ok(html.includes(`aria-label="${esc(label)}"`));
    assert.ok(html.includes(`title="${esc(label)}"`));
    assert.ok(!html.includes(`>${esc(label)}<`), 'share label stays available to assistive technology without visible copy');
    assert.ok(html.includes(`>${share}%</bdi>`));
    assert.ok(html.includes(`stroke-dasharray="${dash}"`));
    assert.match(html, /<svg[^>]*aria-hidden="true"[^>]*focusable="false"/);
  }
  for (const share of [-20, 120]) {
    const html = accountShareBadge(share);
    const text = html.match(/<bdi[^>]*>(.*?)<\/bdi>/)[1].replace(/[\u061c\u200e\u200f]/g, '');
    assert.equal(text, `${share}%`, 'signed or oversized shares must stay accurate');
    assert.ok(!html.includes('<svg'), 'out-of-range shares cannot look like valid donut charts');
    assert.ok(html.includes(`title="${esc(label)}"`));
  }
  for (const share of [undefined, null, NaN, Infinity, -Infinity]) {
    const html = accountShareBadge(share);
    assert.ok(!html.includes('<svg'));
    assert.ok(html.includes(`title="${esc(label)}"`));
    assert.ok(html.includes(language === 'he' ? 'לא זמין' : 'Not available'));
    assert.match(html, /account-share-ring-placeholder" aria-hidden="true"/);
    assert.ok(!html.includes('NaN') && !html.includes('Infinity'));
  }
}
''',
    ])
    result = subprocess.run(["node"], input=script, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
