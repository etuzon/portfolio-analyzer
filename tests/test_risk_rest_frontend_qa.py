"""Production HTML and handlers with synthetic receipts in disposable Chromium.

These tests verify interaction and localization, separately from actual live
HTTPS, model and Internet acceptance.
"""
import base64

import pytest

from test_account_cash_update_qa import browser_wait
from test_native_account_history_qa import chromium
from test_risk_progress_independent_qa import ready
from test_risk_scale_v4_browser_qa import press


@pytest.mark.parametrize("language,width", [("en",1440),("he",390)])
def test_failed_retry_keeps_frozen_request_and_supports_keyboard(tmp_path, chromium, language, width):
    command, evaluate = ready(tmp_path, chromium, language, width)
    evaluate("""
qa.job.status='failed';qa.job.code='request_limit';qa.job.failure={code:'request_limit'};
qa.job.position_scope='all';qa.job.security_keys=['BBDC|NYSE|USD'];qa.job.data_types=['risk_inputs'];
qa.job.refresh_policy='refresh_existing';qa.job.risk_mode='api';
qa.job.progress={stage:'failed',completed:5,total:27,current_security:{symbol:'BBDC'}};
qa.job.risk_inputs.status='failed';qa.advance();
""")
    browser_wait(evaluate,"!$('retryRiskRetrieval').disabled")
    assert evaluate("$('riskRetrievalFailure').hidden") is False
    assert evaluate("$('riskRetrievalFailure').getAttribute('role')") == "alert"
    failure = evaluate("$('riskRetrievalFailure').textContent")
    assert ("budget" if language == "en" else "מגבלת הבקשות") in failure
    assert evaluate("$('retryRiskRetrieval').textContent") == ("Retry remaining checks" if language == "en" else "ניסיון חוזר לבדיקות שנותרו")
    assert evaluate("$('riskRetrievalDiagnostics').hidden") is False
    assert evaluate("$('riskRetrievalDiagnosticsLink').getAttribute('href')") == "/api/securities/enrichment/ai/independent-27/diagnostics"
    assert "independent-27" in evaluate("$('riskRetrievalRequestId').textContent")
    evaluate("$('riskRetrievalDiagnostics').open=true;$('riskRetrievalMode').value='ai';$('riskRetrievalScope').value='selected';$('riskRetrievalScope').dispatchEvent(new Event('change',{bubbles:true}))")
    assert evaluate("$('riskRetrievalSecurities').querySelectorAll('input:checked').length") == 0
    assert evaluate("document.documentElement.scrollWidth-innerWidth") <= 1
    evaluate("$('retryRiskRetrieval').scrollIntoView({block:'center'});$('retryRiskRetrieval').focus()")
    assert evaluate("document.activeElement.id") == "retryRiskRetrieval"
    press(command,"Enter","Enter",13,"\r")
    browser_wait(evaluate,"qa.writes.length===1")
    assert evaluate("qa.writes[0]") == {"path":"/api/securities/enrichment/ai","method":"POST","body":{
        "resume_request_id":"independent-27","security_keys":["BBDC|NYSE|USD"],"data_types":["risk_inputs"],
        "position_scope":"all","refresh_policy":"refresh_existing","risk_mode":"api"}}
    assert evaluate("qa.errors") == []
    if language == "he":
        visible = evaluate("$('riskRetrievalModal').innerText")
        for phrase in ("Request diagnostics","View request diagnostics","Request ID:","Retry remaining checks","request budget"):
            assert phrase not in visible
    (tmp_path / f"failed-risk-{language}-{width}.png").write_bytes(base64.b64decode(
        command("Page.captureScreenshot",{"format":"png","captureBeyondViewport":False})["data"]))


@pytest.mark.parametrize("language", ["en","he"])
def test_failure_reasons_localize_auth_timeout_and_validation(tmp_path, chromium, language):
    _, evaluate = ready(tmp_path, chromium, language)
    for code in ("authentication_expired","ai_provider_timeout","proposal_invalid","job_failed"):
        evaluate(f"qa.job.status='failed';qa.job.code={code!r};qa.job.failure={{code:{code!r}}};qa.job.progress.stage='failed';$('checkRiskRetrieval').click()")
        browser_wait(evaluate,"!$('checkRiskRetrieval').disabled")
        text = evaluate("$('riskRetrievalFailure').textContent")
        assert text and "private" not in text and code not in text
        if language == "he":
            assert any("\u0590" <= char <= "\u05ff" for char in text), text
            for phrase in ("The session expired","The AI check","The research request","Saved results"):
                assert phrase not in text
    help_prefix = "Failed requests show a reason" if language == "en" else "בקשות שנכשלו מציגות סיבה"
    help_text = evaluate("[...document.querySelectorAll('p')].find(element=>element.textContent.includes(" + repr(help_prefix) + ")).textContent")
    for phrase in (("completed checks are skipped", "failed AI check remains eligible", "read-only receipt", "restarting or deploying")
                   if language == "en" else ("בדיקות שהושלמו אינן חוזרות", "שנכשלה נשארת מתאימה לניסיון חוזר", "לקריאה בלבד", "הפעלה מחדש או פריסה")):
        assert phrase in help_text
    if language == "he":
        assert "Request diagnostics" not in help_text and "Retry remaining checks" not in help_text
    assert evaluate("qa.errors") == []
