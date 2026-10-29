import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_events_show_localized_structured_details_without_internal_source_keys():
    source = (ROOT / "web/app.js").read_text()
    start = source.index("function renderEvents(")
    end = re.search(r"\n(?:async )?function ", source[start + 1:])
    function = source[start:start + 1 + end.start()]
    script = "const window = {};\n" + (ROOT / "web/i18n.js").read_text() + function + """
      const assert = require('node:assert/strict');
      const nodes = {};
      const $ = (id) => nodes[id] ||= {};
      const state = {language: 'he', baseCurrency: 'USD', localEvents: [],
        eventDividendSettings: {start_date: '2026-08-01', tax_rate: 0.25, next_run: '2026-10-30T07:00:00Z'}};
      const t = (text) => window.PortfolioI18n.translate(text, state.language);
      const esc = (text) => String(text).replaceAll('<', '&lt;').replaceAll('"', '&quot;');
      const formatDate = (value) => value ? value.split('-').reverse().join('/') : '—';
      const pct = (value) => `${value}%`;
      const fmt = (value) => String(value);
      const money = (value, currency, digits) => `${currency} ${Number(value).toFixed(digits)}`;
      const event = {id: 'event-1', type: 'DIVIDEND', status: 'processed', symbol: 'SAR', event_date: '2026-08-05',
        account_label: 'Schwab', account_db_id: 'internal-account-uuid', transaction_id: 'tx-1',
        currency: 'USD', gross_amount: 25.25, tax_amount: 6.31, net_amount: 18.94,
        source_key: 'dividend:internal-account-uuid:SAR:YAHOO:2026-08-05:999999.0000000000',
        details: {shares: 101, gross_per_share: 0.25}};
      state.localEvents = [event];
      const original = JSON.stringify(event);
      renderEvents();
      const hebrew = nodes.eventsList.innerHTML;
      assert.ok(hebrew.includes('דיבידנד SAR'));
      assert.ok(hebrew.includes('התשלום נרשם'));
      assert.ok(hebrew.includes('ברוטו: USD 25.25'));
      assert.ok(hebrew.includes('מס: USD 6.31'));
      assert.ok(hebrew.includes('נטו: USD 18.94'));
      assert.ok(hebrew.includes('מניות: 101'));
      assert.ok(hebrew.includes('דיבידנד למניה: USD 0.2500'));
      assert.ok(hebrew.includes('עריכת פעולה'));
      assert.ok(hebrew.includes('data-edit-security="tx-1"'));
      assert.ok(!/processed|DIVIDEND|Gross|Tax|Net|dividend:|internal-account-uuid|999999/u.test(hebrew));
      assert.ok(nodes.eventsStatus.textContent.includes('01/08/2026'));
      assert.ok(nodes.eventsStatus.textContent.includes('30/10/2026'));
      assert.ok(!/[A-Za-z]/u.test(nodes.eventsStatus.textContent));
      state.language = 'en';
      renderEvents();
      assert.ok(nodes.eventsList.innerHTML.includes('Payment recorded'));
      assert.ok(nodes.eventsList.innerHTML.includes('Dividend per share'));
      assert.ok(!/[א-ת]/u.test(nodes.eventsList.innerHTML + nodes.eventsStatus.textContent));
      state.language = 'he';
      renderEvents();
      assert.equal(nodes.eventsList.innerHTML, hebrew);
      assert.equal(JSON.stringify(event), original, 'localization must preserve API data and duplicate-prevention keys');
      state.localEvents = [{...event, status: 'pending', details: {}, account_label: event.account_db_id}];
      renderEvents();
      assert.ok(nodes.eventsList.innerHTML.includes('ממתין'));
      assert.ok(nodes.eventsList.innerHTML.includes('החשבון אינו זמין'));
      assert.ok(!/internal-account-uuid|undefined|NaN|דיבידנד למניה/u.test(nodes.eventsList.innerHTML));
      state.localEvents = [];
      renderEvents();
      assert.ok(nodes.eventsList.innerHTML.includes('אין אירועים'));
    """
    subprocess.run(["node"], input=script, check=True, capture_output=True, text=True)
