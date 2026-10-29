import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_confirmed_sale_clears_form_and_updates_history_before_analytics_finishes():
    source = (ROOT / "web/app.js").read_text()
    functions = []
    for name in (
        "savePositionTransaction", "clearPositionTransactionForm", "renderPositionTransactionHistory",
        "positionTransactionDisplayAction", "transactionMatchesPosition", "transactionMatchesSecurity",
    ):
        match = re.search(rf"(?:async )?function {name}\(", source)
        end = re.search(r"\n(?:async )?function ", source[match.end():])
        functions.append(source[match.start():match.end() + end.start()])
    script = "const window = {};\n" + (ROOT / "web/i18n.js").read_text()
    script += "\n".join(functions) + """
      const assert = require('node:assert/strict');
      const nodes = {};
      const $ = (id) => nodes[id] ||= {value: ''};
      const t = (text) => window.PortfolioI18n.translate(text, state.language);
      const state = {language: 'he', editingPositionTransactionId: '', localTransactions: []};
      const canWrite = () => true;
      const esc = (value) => String(value);
      const fmt = (value) => String(value);
      const money = (value) => String(value);
      const cleanSourceLabel = (value) => value;
      const cleanSecuritySymbol = (value) => String(value || '').toUpperCase();
      const formatDate = (value) => value.split('-').reverse().join('/');
      const todayString = () => '2026-10-29';
      const setDateField = (id, value) => {$(id).value = value;};
      const valueOf = (id) => $(id).value;
      const syncPositionTransactionLimit = () => {};
      const refreshPositionTransactionDetail = () => {};
      const positionTransactionEditingRow = () => state.localTransactions.find((tx) => tx.id === state.editingPositionTransactionId);
      const validatePositionTransactionForm = () => ({action: 'SELL', quantity: 17, price: 62.11, tradeDate: '2026-10-29'});
      let resolveWrite, rejectWrite, rejectRefresh;
      let writes = 0, refreshes = 0;
      const api = () => {writes++; return new Promise((resolve, reject) => {resolveWrite = resolve; rejectWrite = reject;});};
      const loadPortfolio = () => {refreshes++; return new Promise((_resolve, reject) => {rejectRefresh = reject;});};
      const tick = () => new Promise((resolve) => setImmediate(resolve));
      const buy = {id: 'original-buy', account_db_id: 'acct', symbol: 'BRKR', stock_market: 'NASDAQ',
        action: 'ADD', comments: 'Imported source BUY', source: 'portfolio_import', quantity: 17, price: 56.9912,
        currency: 'USD', trade_date: '2026-04-07', created_at: '2026-04-07T12:00:00Z'};
      const sale = {id: 'confirmed-sale', account_db_id: 'acct', symbol: 'BRKR', stock_market: 'NASDAQ',
        action: 'SELL', quantity: 17, price: 62.11, currency: 'USD', trade_date: '2026-10-29',
        created_at: '2026-10-29T12:00:00Z', position_quantity: 0, position_closed: true};
      (async () => {
        state.positionTransactionsDetail = {symbol: 'BRKR', market: 'NASDAQ', accountId: 'acct',
          account: 'Schwab', currency: 'USD', quantity: 17, average: 56.99};
        state.localTransactions = [buy];
        $('positionTransactionQuantity').value = '17';
        $('positionTransactionPrice').value = '62.11';
        $('positionTransactionComments').value = 'Sell all';
        const saving = savePositionTransaction();
        assert.ok($('savePositionTransaction').disabled);
        await savePositionTransaction();
        assert.equal(writes, 1, 'repeated clicks while saving cannot submit twice');
        assert.equal(valueOf('positionTransactionQuantity'), '17', 'retain inputs until save is confirmed');
        resolveWrite(sale);
        await saving;
        assert.equal(refreshes, 1);
        for (const id of ['positionTransactionQuantity', 'positionTransactionPrice', 'positionTransactionComments']) {
          assert.equal(valueOf(id), '', 'clear inputs immediately after confirmed save');
        }
        assert.ok($('positionTransactionStatus').textContent.includes('הפעולה נוספה בהצלחה.'));
        assert.ok($('positionTransactionStatus').textContent.includes('ההחזקה נסגרה.'));
        assert.equal(state.positionTransactionsDetail.quantity, 0, 'keep closed position history visible');
        let history = $('positionTransactionsRows').innerHTML;
        assert.ok(history.indexOf('confirmed-sale') < history.indexOf('original-buy'));
        assert.ok(history.includes('מכירה') && history.includes('קנייה'));
        assert.ok($('positionTransactionsSubtitle').textContent.includes('0 יחידות'));
        rejectRefresh(new TypeError('Failed to fetch'));
        await tick();
        assert.ok($('positionTransactionStatus').textContent.includes('הפעולה נשמרה'));
        assert.ok(!$('positionTransactionStatus').textContent.includes('Failed to fetch'));
        assert.equal($('positionTransactionsRows').innerHTML, history, 'analytics failure must retain confirmed row');
        assert.ok(!$('savePositionTransaction').disabled);

        // Same-day trades are ordered by creation time, newest first.
        state.localTransactions = [{...buy, trade_date: sale.trade_date}, sale];
        renderPositionTransactionHistory();
        history = $('positionTransactionsRows').innerHTML;
        assert.ok(history.indexOf('confirmed-sale') < history.indexOf('original-buy'));

        // Editing replaces the saved row rather than adding a duplicate.
        state.editingPositionTransactionId = sale.id;
        const editing = savePositionTransaction();
        resolveWrite({...sale, price: 63});
        await editing;
        assert.equal(state.localTransactions.filter((tx) => tx.id === sale.id).length, 1);
        assert.ok($('positionTransactionStatus').textContent.includes('הפעולה עודכנה בהצלחה.'));

        // An unconfirmed save must keep the entered values and never invent a row.
        $('positionTransactionQuantity').value = '2';
        $('positionTransactionPrice').value = '65';
        const count = state.localTransactions.length;
        const failure = savePositionTransaction();
        rejectWrite(new TypeError('Failed to fetch'));
        await assert.rejects(failure, /לא ניתן לאמת את השמירה/);
        assert.equal(valueOf('positionTransactionQuantity'), '2');
        assert.equal(valueOf('positionTransactionPrice'), '65');
        assert.equal(state.localTransactions.length, count);
        assert.ok(!state.positionTransactionSaving);
        assert.ok(!$('savePositionTransaction').disabled);
      })().catch((error) => {console.error(error); process.exitCode = 1;});
    """
    subprocess.run(["node"], input=script, check=True, capture_output=True, text=True)
