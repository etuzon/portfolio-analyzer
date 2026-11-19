"""Independent rendered EN/HE startup feedback; synthetic REST, real Chromium."""
import json
import pytest
from test_account_cash_update_qa import browser_wait
from test_ai_research_schedules_browser_qa import fixture
from test_native_account_history_qa import chromium


@pytest.mark.parametrize('language,width', [('en', 1440), ('he', 390)])
def test_risk_inventory_preparation_never_claims_zero_checked(tmp_path, chromium, language, width):
    command, evaluate = chromium
    command('Emulation.setDeviceMetricsOverride', {'width': width, 'height': 1000,
        'deviceScaleFactor': 1, 'mobile': False})
    command('Page.navigate', {'url': fixture(tmp_path, language).as_uri()})
    browser_wait(evaluate, 'window.qa?.aiReady===true||!!window.qa?.errors?.length')
    job = {'request_id': 'startup-feedback-qa', 'data_types': ['risk_inputs'], 'status': 'running',
        'progress': {'stage': 'capturing_inventory', 'completed': 0, 'total': 0},
        'coverage': {'total_candidates': 0}, 'risk_inputs': {'status': 'queued', 'outcomes': []}}
    evaluate('qa.lastParent=' + json.dumps(job) + ";document.querySelector('[data-open-risk-input-retrieval]').click()")
    browser_wait(evaluate, "!$('riskRetrievalModal').hidden&&!$('reloadRiskRetrieval').disabled&&$('riskRetrievalStatus').textContent.includes(" + json.dumps('Preparing' if language == 'en' else 'מכין') + ')')
    status = evaluate("$('riskRetrievalStatus').textContent")
    assert status == ('Preparing research inventory…' if language == 'en' else 'מכין את רשימת ניירות הערך למחקר…')
    assert evaluate("$('riskRetrievalCoverage').textContent") == ''
    evaluate("qa.lastParent.status='failed';qa.lastParent.progress.stage='failed';qa.lastParent.failure={stage:'capturing_inventory',code:'check_incomplete'};qa.retrieval=qa.lastParent;$('checkRiskRetrieval').click()")
    browser_wait(evaluate, "!$('riskRetrievalFailure').hidden&&!$('checkRiskRetrieval').disabled")
    error = evaluate("$('riskRetrievalFailure').textContent")
    assert ('No securities were checked' if language == 'en' else 'לא נבדקו ניירות') in error
    assert evaluate("$('riskRetrievalCoverage').textContent") == ''
    assert evaluate("$('riskRetrievalStatus').textContent") == ('Failed' if language == 'en' else 'נכשל')
    assert evaluate("$('retryRiskRetrieval').hidden||$('retryRiskRetrieval').disabled") is False
    assert evaluate("$('riskRetrievalDiagnosticsLink').getAttribute('href')") == '/api/securities/enrichment/ai/startup-feedback-qa/diagnostics'
    if language == 'he':
        assert 'Research' not in error and 'securities' not in error
    assert evaluate('qa.errors') == []
