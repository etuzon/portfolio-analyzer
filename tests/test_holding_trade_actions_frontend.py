import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_trade_actions_preserve_account_and_enforce_position_side_and_limits():
    source = (ROOT / "web/app.js").read_text()
    functions = []
    for name in (
        "holdingTransactionActions", "holdingTransactionActionLabel", "holdingTransactionActionsHtml",
        "positionTransactionEditingRow", "positionTransactionAvailableQuantity", "syncPositionTransactionLimit",
        "clearPositionTransactionForm", "validatePositionTransactionForm", "openPositionTransactionHistory",
        "savePositionTransaction",
    ):
        match = re.search(rf"(?:async )?function {name}\(", source)
        end = re.search(r"\n(?:async )?function ", source[match.end():])
        functions.append(source[match.start():match.end() + end.start()])
    script = "const window = {};\n" + (ROOT / "web/i18n.js").read_text()
    script += "\n".join(functions) + """
      const assert = require('node:assert/strict');
      const state = {language: 'he', localTransactions: [], baseCurrency: 'ILS'};
      let writable = true;
      const canWrite = () => writable;
      const t = (text) => window.PortfolioI18n.translate(text, state.language);
      const esc = (text) => String(text).replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;');
      const cleanSourceLabel = (text) => text;
      const cleanSecuritySymbol = (text) => text.toUpperCase();
      const holdingMarketKey = (holding) => holding.stock_market;
      const fmt = (number) => String(number);
      const nodes = {};
      const $ = (id) => nodes[id] ||= {value: '', removeAttribute(name) {delete this[name];}, focus() {this.focused = true;}};
      $('positionTransactionAction').options = ['BUY', 'SELL', 'SHORT'].map((value) => ({value}));
      const valueOf = (id) => $(id).value;
      const setDateField = (id, value) => {$(id).value = value;};
      const todayString = () => '2026-10-29';
      const dateValue = () => '2026-10-29';
      const DATE_PLACEHOLDER = 'dd/mm/yyyy';
      const holding = {symbol: 'BRKR', account_id: 'local-account-2', account: 'Schwab "joint"',
        stock_market: 'NASDAQ', quantity: 17, cost_basis: 969, asset_class: 'EQUITY', currency: 'USD', location: 'USA'};
      assert.deepEqual(holdingTransactionActions(17), ['BUY', 'SELL']);
      assert.deepEqual(holdingTransactionActions(-5), ['SHORT', 'BUY']);
      assert.deepEqual(holdingTransactionActions(0), ['BUY']);
      assert.deepEqual(holdingTransactionActions(NaN), []);
      let html = holdingTransactionActionsHtml(holding);
      assert.ok(html.includes('data-position-action="SELL"'));
      assert.ok(!html.includes('data-position-action="SHORT"'));
      assert.ok(html.includes('data-position-history-account-id="local-account-2"'));
      assert.ok(html.includes('data-position-history-market="NASDAQ"'));
      assert.ok(html.includes('Schwab &quot;joint&quot;'));
      assert.ok(html.includes('קנייה') && html.includes('מכירה'));
      html = holdingTransactionActionsHtml({...holding, quantity: -5});
      assert.ok(html.includes('הגדלת שורט') && html.includes('קנייה לסגירת שורט'));
      assert.ok(!html.includes('data-position-action="SELL"'));
      state.language = 'en';
      html = holdingTransactionActionsHtml({...holding, quantity: -5});
      assert.ok(html.includes('Buy to cover') && html.includes('Add short'));
      assert.ok(!/[א-ת]/u.test(html));
      writable = false;
      assert.equal(holdingTransactionActionsHtml(holding), '');
      writable = true;
      assert.equal(holdingTransactionActionsHtml({...holding, account_id: ''}), '');

      let opened = 0;
      let saved;
      let refreshed = 0;
      const openModal = () => {opened++;};
      const closeModal = () => {};
      const renderPositionTransactionHistory = () => {};
      const refreshPositionTransactionDetail = (quantity) => {state.positionTransactionsDetail.quantity = quantity;};
      const loadPortfolio = async () => {refreshed++;};
      const api = async (path, options) => {
        if (!options) return {items: []};
        assert.equal(path, '/api/local/securities');
        assert.equal(options.method, 'POST');
        saved = JSON.parse(options.body);
        return {position_quantity: 16, position_closed: false};
      };
      const context = {positionAction: 'SELL', positionHistorySymbol: 'BRKR', positionHistoryMarket: 'NASDAQ',
        positionHistoryAccountId: 'local-account-2', positionHistoryAccount: 'Schwab', positionHistoryCurrency: 'USD',
        positionHistoryQuantity: '17', positionHistoryAsset: 'EQUITY', positionHistoryLocation: 'USA'};
      (async () => {
        await openPositionTransactionHistory(context);
        assert.equal(opened, 1);
        assert.equal(valueOf('positionTransactionAction'), 'SELL');
        assert.equal($('positionTransactionQuantity').max, '17');
        assert.ok($('positionTransactionQuantity').focused);
        assert.ok($('positionTransactionAction').options.find((option) => option.value === 'SHORT').disabled);
        $('positionTransactionQuantity').value = '18';
        $('positionTransactionPrice').value = '56';
        assert.throws(validatePositionTransactionForm, /sell at most 17/);
        $('positionTransactionQuantity').value = '1';
        await savePositionTransaction();
        assert.equal(saved.account_db_id, 'local-account-2');
        assert.equal(saved.symbol, 'BRKR');
        assert.equal(saved.action, 'SELL');
        assert.equal(saved.stock_market, 'NASDAQ');
        assert.equal(saved.currency, 'USD');
        assert.equal(refreshed, 1);

        await openPositionTransactionHistory({...context, positionAction: 'SHORT'});
        assert.equal(opened, 1, 'cannot open a short action on a long row');
        await openPositionTransactionHistory({...context, positionAction: 'BUY', positionHistoryQuantity: '-5'});
        assert.equal($('positionTransactionQuantity').max, '5');
        assert.ok($('positionTransactionAction').options.find((option) => option.value === 'SELL').hidden);
        $('positionTransactionQuantity').value = '6';
        assert.throws(validatePositionTransactionForm, /buy at most 5/);
        $('positionTransactionQuantity').value = '5';
        assert.equal(validatePositionTransactionForm().action, 'BUY');
        $('positionTransactionAction').value = 'SELL';
        assert.throws(validatePositionTransactionForm, /unavailable/);
        $('positionTransactionAction').value = 'SHORT';
        syncPositionTransactionLimit();
        assert.equal($('positionTransactionQuantity').max, undefined);
        assert.equal(validatePositionTransactionForm().action, 'SHORT');
        writable = false;
        await openPositionTransactionHistory(context);
        assert.equal(opened, 2, 'viewer cannot open a trade action');
      })().catch((error) => {console.error(error); process.exitCode = 1;});
    """
    subprocess.run(["node"], input=script, check=True, capture_output=True, text=True)


def test_holdings_rows_include_compact_trade_actions_and_permission_controls():
    script = (ROOT / "web/app.js").read_text()
    styles = (ROOT / "web/styles.css").read_text()
    assert '${holdingTransactionActionsHtml(h)}' in script
    assert '"data-position-action"' in script.split("const WRITE_DATA_ACTIONS", 1)[1]
    assert '.holding-transaction-actions button' in styles
