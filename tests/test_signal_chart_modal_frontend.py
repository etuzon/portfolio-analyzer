"""Behavioral regression for opening a price chart above its originating signals."""
from pathlib import Path
import re
import subprocess


SOURCE = (Path(__file__).resolve().parents[1] / "web/app.js").read_text()


def js_functions(*names):
    result = []
    for name in names:
        start = re.search(rf"^(?:async )?function {name}\(", SOURCE, re.M).start()
        end = re.search(r"^}", SOURCE[start:], re.M).end()
        result.append(SOURCE[start:start + end])
    return "\n".join(result)


def test_signal_chart_is_topmost_immediately_and_returns_to_signals_after_close():
    start = SOURCE.index('document.addEventListener("keydown", (event) => {')
    end = SOURCE.index('\ndocument.addEventListener("click",', start)
    script = r"""
const assert = require('node:assert/strict');
let keydown;
const document = {
  activeElement: null,
  addEventListener(type, callback) { if (type === 'keydown') keydown = callback; },
  querySelectorAll(selector) {
    assert.equal(selector, '.modal:not([hidden])');
    return order.filter(modal => !modal.hidden);
  },
  querySelector() { return null; },
};
class HTMLElement {
  constructor(id, parent = null) {
    this.id = id; this.parent = parent; this.hidden = false; this.inert = false;
    this.isConnected = true; this.dataset = {}; this.attributes = {};
  }
  closest(selector) {
    if (selector === '.modal:not([hidden])') return this.parent?.hidden ? null : this.parent;
    return null;
  }
  focus(options) { document.activeElement = this; this.focusOptions = options; }
  setAttribute(key, value) { this.attributes[key] = value; }
  removeAttribute(key) { delete this.attributes[key]; }
  getClientRects() { return [1]; }
  querySelector(selector) { return selector === 'button[data-close]' ? this.controls?.[0] : null; }
  querySelectorAll() { return this.controls || []; }
}
const research = new HTMLElement('researchModal');
research.scrollTop = 420;
const chart = new HTMLElement('securityDetailModal');
chart.hidden = true;
const order = [chart, research]; // The actual HTML puts research later than the chart.
const parent = {append(modal) { order.splice(order.indexOf(modal), 1); order.push(modal); }};
chart.parentElement = parent;
research.parentElement = parent;
const chartClose = new HTMLElement('chartClose', chart);
const chartPeriod = new HTMLElement('chartPeriod', chart);
chart.controls = [chartClose, chartPeriod];
const trigger = new HTMLElement('signalChart', research);
trigger.dataset.alertChart = 'NEWT';
const nodes = {researchModal: research, securityDetailModal: chart,
  detailPriceInput: {}, detailPriceComments: {}};
const $ = id => nodes[id] || null;
const modalReturnFocus = new Map();
const state = {items: [{holding: {symbol: 'NEWT', stock_market: 'NASDAQ',
  asset_class: 'EQUITY', currency: 'USD', country: 'USA'}}]};
const requestAnimationFrame = callback => callback();
const mountModalHomeLink = () => {};
const focusModalDestination = () => {};
const cleanSecuritySymbol = value => String(value || '').toUpperCase();
const holdingMarketKey = holding => holding.stock_market;
const stockMarketDisplay = holding => holding.stock_market;
const dataProviderDisplay = () => 'cached';
const securityMatches = (item, symbol, market) => item.holding.symbol === symbol && item.holding.stock_market === market;
const clampedHistoryDate = value => value;
const resetSecurityChartZoom = () => {};
const setDateField = () => {};
const todayString = () => '2026-10-30';
let completeHistory;
const loadSecurityDetail = () => new Promise(resolve => { completeHistory = resolve; });
const event = (key, shiftKey = false) => ({key, shiftKey, target: document.activeElement,
  preventDefault() { this.prevented = true; }});
""" + js_functions("openAlertSignalChart", "openSecurityDetail", "openModal", "closeModal") + SOURCE[start:end] + r"""
(async () => {
  // Explicit returnFocus must work even when the browser has focused something else.
  document.activeElement = new HTMLElement('dashboard');
  const loading = openAlertSignalChart('NEWT', trigger);
  assert.equal(chart.hidden, false, 'chart shell should appear before network completion');
  assert.equal(order.at(-1), chart, 'the chart must paint above research');
  assert.equal(research.hidden, false, 'preserve the signal screen and scroll context');
  assert.equal(research.inert, true);
  assert.equal(research.attributes['aria-hidden'], 'true');
  assert.equal(document.activeElement, chartClose, 'focus enters the visible chart');
  assert.equal(modalReturnFocus.get(chart.id), trigger);
  assert.equal(state.securityDetail.symbol, 'NEWT');
  const backward = event('Tab', true);
  keydown(backward);
  assert.equal(backward.prevented, true);
  assert.equal(document.activeElement, chartPeriod, 'keyboard trap belongs to the front chart');
  keydown(event('Tab'));
  assert.equal(document.activeElement, chartClose);
  completeHistory();
  await loading;
  keydown(event('Escape'));
  assert.equal(chart.hidden, true, 'Escape closes only the front chart');
  assert.equal(research.hidden, false);
  assert.equal(research.inert, false);
  assert.equal(research.attributes['aria-hidden'], undefined);
  assert.equal(research.scrollTop, 420);
  assert.equal(document.activeElement, trigger, 'return to the originating signal action');
  assert.equal(trigger.focusOptions.preventScroll, true);
  assert.equal(chart.dataset.parentModalId, undefined);

  // Reopening from the dashboard must not retain the previous signals parent.
  research.hidden = true;
  const dashboardTrigger = new HTMLElement('holdingChart');
  const second = openSecurityDetail({securityDetailSymbol: 'NEWT', securityDetailMarketKey: 'NASDAQ'}, dashboardTrigger);
  assert.equal(chart.dataset.parentModalId, undefined);
  completeHistory();
  await second;
  closeModal(chart);
  assert.equal(document.activeElement, dashboardTrigger);
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
    result = subprocess.run(["node"], input=script, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
