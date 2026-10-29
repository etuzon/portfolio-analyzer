import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_run_updates_retry_after_disconnect_and_stop_at_completion():
    source = (ROOT / "web/app.js").read_text()
    functions = []
    for name in ("renderAlerts", "alertRunIsActive", "scheduleAlertRefresh", "loadAlerts"):
        start = source.index(f"function {name}(")
        if source[start - 6:start] == "async ":
            start -= 6
        end = source.index("\nfunction ", start + 10)
        # loadAlerts is followed by another async function.
        async_end = source.find("\nasync function ", start + 10)
        if async_end != -1:
            end = min(end, async_end)
        functions.append(source[start:end])
    script = "\n".join(functions) + """
      const assert = require('node:assert/strict');
      const state = {alertConditions: [1], alertRefreshTimer: null};
      const nodes = {};
      const $ = (id) => nodes[id] ||= {};
      const t = (text) => text;
      const fmt = (number) => String(number);
      const esc = (text) => String(text);
      const formatDateTime = () => '29/10/2026, 21:47';
      const renderAlertConditions = () => {};
      const alertRunStatusText = (status) => status;
      const alertRunProgressText = (progress) => `${progress.completed}/${progress.total}`;
      const pending = new Map();
      let timerId = 0;
      const window = {setTimeout: (callback) => {
        pending.set(++timerId, callback);
        return timerId;
      }};
      const clearTimeout = (id) => pending.delete(id);
      async function tick() {
        assert.equal(pending.size, 1, 'exactly one refresh should be scheduled');
        const [id, callback] = pending.entries().next().value;
        pending.delete(id);
        await callback();
      }
      const running = (completed) => ({rules: [], runs: [{
        status: 'running', progress: {completed, total: 27}
      }]});
      let requests = 0;
      const api = async (path) => {
        assert.equal(path, '/api/alerts');
        requests++;
        if (requests === 1) throw new Error('temporary disconnect');
        if (requests === 2) return running(26);
        return {rules: [], runs: [{status: 'completed', evaluated_symbols: 27}]};
      };
      (async () => {
        renderAlerts(running(20));
        assert.ok(nodes.alertRunHistory.innerHTML.includes('20/27'));
        await tick();
        assert.equal(nodes.alertStatus.textContent, 'Connection interrupted. Retrying run updates…');
        await tick();
        assert.ok(nodes.alertRunHistory.innerHTML.includes('26/27'));
        assert.equal(nodes.alertStatus.textContent, 'Running your saved portfolio rule…');
        await tick();
        assert.ok(nodes.alertRunHistory.innerHTML.includes('completed'));
        assert.ok(!nodes.alertRunHistory.innerHTML.includes('signal-run-progress'));
        assert.equal(nodes.alertStatus.textContent, 'Rule check finished.');
        assert.equal(state.alertRefreshTimer, null);
        assert.equal(pending.size, 0);
        assert.equal(requests, 3);

        // Repeated renders replace the pending refresh rather than duplicating it.
        renderAlerts(running(0));
        renderAlerts(running(1));
        assert.equal(pending.size, 1);
        renderAlerts({rules: [], runs: [{status: 'failed'}]});
        assert.equal(nodes.alertStatus.textContent, 'Rule check failed.');
        assert.equal(pending.size, 0);
        assert.ok(alertRunIsActive({rules: [{last_status: 'Running'}]}));
        assert.ok(alertRunIsActive({rules: [{last_status: 'running'}]}));
      })().catch((error) => {console.error(error); process.exitCode = 1;});
    """
    subprocess.run(["node"], input=script, check=True, capture_output=True, text=True)
