"""Safe Markdown formatting of assistant answers using synthetic financial examples."""
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def _run(script):
    code = "const window={}; const assert=require('node:assert/strict');\n"
    code += (ROOT / "web/assistant-format.js").read_text()
    code += "\nconst format=window.PortfolioAssistantFormat;\n" + script
    result = subprocess.run(["node"], input=code, text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr


def test_markdown_blocks_lists_emphasis_and_code_are_scannable():
    _run(r"""
const text='# Portfolio summary\n\nRevenue is **$1,234.50** and *growing*.\nDate: `31/12/2025`.\n\n3. Review concentration\n4. Check dividends\n  - Keep the latest amount\n\n> **Note:** values are in USD.\n\n```text\nline 1\nline 2\n```';
const html=format.render(text);
assert.ok(html.includes('<h4>Portfolio summary</h4>'));
assert.ok(html.includes('<strong>$1,234.50</strong>'));
assert.ok(html.includes('<em>growing</em>'));
assert.ok(html.includes('<code>31/12/2025</code>'));
assert.ok(html.includes('<ol start="3">'));
assert.ok(html.includes('<ul>'));
assert.ok(html.includes('<blockquote>'));
assert.ok(html.includes('line 1\nline 2'));
assert.ok(html.includes('tabindex="0" role="region"'));
""")


def test_financial_tables_preserve_cells_alignment_and_bidirectional_isolation():
    _run(r"""
const html=format.render('| Company | Amount | Change |\n| :--- | ---: | :---: |\n| דוגמה | ₪1,234.50 | :positive[+12.5%] |\n| A\\|B | `x|y` | :negative[-2%] | extra value |', {tableLabel:'טבלת תשובה',columnLabel:'עמודה {count}'});
assert.ok(html.includes('role="region" tabindex="0" aria-label="טבלת תשובה"'));
assert.ok(html.includes('<thead>')&&html.includes('<tbody>')&&html.includes('scope="col"'));
assert.ok(html.includes('assistant-align-left')&&html.includes('assistant-align-right')&&html.includes('assistant-align-center'));
assert.ok(html.includes('<bdi dir="auto">₪1,234.50</bdi>'));
assert.ok(html.includes('A|B')&&html.includes('<code>x|y</code>'));
assert.ok(html.includes('extra value')&&html.includes('עמודה 4'));
assert.ok(html.includes('+12.5%')&&html.includes('-2%'));
""")


def test_json_pretty_print_does_not_reserialize_or_round_any_token():
    _run(r"""
const raw='{"large":9007199254740993123456789,"decimal":0.123456789012345678901,"exponent":1.2300e-123,"negativeZero":-0,"date":"31/12/2025","currency":"₪1,234.50","escaped":"a\\nb\\\"c","empty":[]}';
const pretty=format.prettyJson(raw);
assert.ok(pretty.includes('\n  "large": 9007199254740993123456789'));
for(const token of ['0.123456789012345678901','1.2300e-123','-0','31/12/2025','₪1,234.50','"escaped": "a\\nb\\\"c"']) assert.ok(pretty.includes(token),token);
assert.ok(format.render('```json\n'+raw+'\n```').includes('9007199254740993123456789'));
assert.equal(format.prettyJson('{invalid: json}'),'{invalid: json}');
""")


def test_untrusted_html_urls_and_assets_remain_inert_text():
    _run(r"""
const attacks='<img src="https://external.example/pixel" onerror="alert(1)">\n<script>alert(1)</script>\n[x](javascript:alert(1))\n![x](data:image/svg+xml,evil)\n:danger[unsafe]\n```html\n</code></pre><iframe src=x></iframe>\n```';
const html=format.render(attacks);
for(const tag of ['<img','<script','<iframe','<svg','<style','<a ']) assert.ok(!html.includes(tag),tag);
assert.ok(!html.includes('href='));
assert.ok(html.includes('&lt;img')&&html.includes('&lt;script'));
assert.ok(html.includes(':danger[unsafe]'));
assert.ok(html.includes('&lt;/code&gt;&lt;/pre&gt;'));
""")


def test_colors_are_only_explicit_whitelisted_markers_and_keep_signs():
    _run(r"""
const html=format.render(':positive[**+8.25%**] :negative[-2.00%] :warning[Missing data] :info[Recorded] :muted[Not available]\n\nUnchanged balance: $10,000.00.\n\n`:positive[+999%]`');
for(const tone of ['positive','negative','warning','info','muted'])assert.ok(html.includes('assistant-tone-'+tone));
assert.equal((html.match(/class="assistant-tone /g)||[]).length,5);
assert.ok(html.includes('<strong>+8.25%</strong>')&&html.includes('-2.00%'));
assert.ok(html.includes('$10,000.00'));
assert.ok(html.includes('<code>:positive[+999%]</code>'));
assert.ok(!format.render('$10,000.00 and -$500').includes('assistant-tone'));
""")


def test_degenerate_input_falls_back_without_dropping_values_or_amplifying_tables():
    _run(r"""
const malformed=':positive['.repeat(15000)+'tail $123.45';
const markers=format.render(malformed);
assert.ok(markers.endsWith('tail $123.45</p>'));
assert.ok(markers.length<malformed.length+100);
const wide='| value |\n| --- |\n'+('|'+Array(5000).fill('1').join('|')+'|\n')+Array(1000).fill('| 9007199254740993 |').join('\n');
const html=format.render(wide);
assert.ok(!html.includes('<table>'));
assert.ok(html.includes('9007199254740993'));
assert.ok(html.length<wide.length*2);
const deep='['.repeat(10000)+'9007199254740993'+']'.repeat(10000);
assert.equal(format.prettyJson(deep),deep);
const oversized='Numbers remain '+ '1234567890'.repeat(25000);
assert.ok(format.render(oversized).includes(oversized));
""")
