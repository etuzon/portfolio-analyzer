"""Controlled AI errors stay distinct without trusting provider response text."""
from threading import Thread
from types import SimpleNamespace

import httpx
import pytest

from app import codex_bridge
from app.llm_assistant import AssistantError, PortfolioAssistant, assistant_settings


@pytest.mark.parametrize('body,expected', [
    ({'error':{'code':'ai_provider_timeout','message':'private-provider-message'}},'ai_provider_timeout'),
    ({'error':{'code':'ai_provider_busy','message':'private-provider-message'}},'ai_provider_busy'),
    ({'error':{'code':'ai_provider_unavailable','message':'private-provider-message'}},'ai_provider_unavailable'),
    ({'error':{'code':'arbitrary-provider-code','message':'private-provider-message'}},'ai_provider_unavailable'),
    ({'error':{'code':{},'message':'private-provider-message'}},'ai_provider_unavailable'),
    ({'error':{'message':'Local Codex timed out.'}},'ai_provider_timeout'),
    ({'error':{'message':'Local Codex timed out. private-provider-message'}},'ai_provider_timeout'),
    ({'error':{'message':'Claude Code planning turn timed out.'}},'ai_provider_timeout'),
    (['private-provider-message'],'ai_provider_unavailable'),
    ('<html>private-provider-message</html>','ai_provider_unavailable'),
])
def test_failed_provider_response_is_classified_without_echoing_raw_details(monkeypatch,body,expected):
    original=httpx.Client
    transport=httpx.MockTransport(lambda _:(httpx.Response(503,text=body) if isinstance(body,str)
        else httpx.Response(503,json=body)))
    monkeypatch.setattr(httpx,'Client',lambda **_:original(transport=transport,base_url='http://codex-local'))
    assistant=PortfolioAssistant(assistant_settings({'llm':{'provider':'local_codex'}}),{})
    with pytest.raises(AssistantError) as error:
        assistant._call_provider(messages=[],tools=[])
    assert error.value.code==expected
    assert 'private-provider-message' not in str(error.value)
    assert 'sign-in' not in str(error.value) and 'login' not in str(error.value)


@pytest.mark.parametrize('exception,expected', [
    (httpx.ReadTimeout('private-provider-message'),'ai_provider_timeout'),
    (httpx.ConnectError('private-provider-message'),'ai_bridge_unavailable'),
])
def test_transport_timeout_does_not_assert_that_model_or_signin_is_invalid(monkeypatch,exception,expected):
    original=httpx.Client
    def fail(_):raise exception
    monkeypatch.setattr(httpx,'Client',lambda **_:original(transport=httpx.MockTransport(fail),base_url='http://codex-local'))
    assistant=PortfolioAssistant(assistant_settings({'llm':{'provider':'local_codex'}}),{})
    with pytest.raises(AssistantError) as error:
        assistant._call_provider(messages=[],tools=[])
    assert error.value.code==expected and 'private-provider-message' not in str(error.value)


@pytest.mark.parametrize('busy',[False,True])
def test_bridge_http_errors_are_structured_and_release_only_acquired_slots(tmp_path,monkeypatch,busy):
    releases=[]
    monkeypatch.setattr(codex_bridge,'_slots',SimpleNamespace(acquire=lambda **_:not busy,release=lambda:releases.append(True)))
    def fail(*_,**__):
        raise codex_bridge.CodexBridgeError('Local Codex timed out.',code='ai_provider_timeout')
    monkeypatch.setattr(codex_bridge,'codex_completion',fail)
    path=tmp_path/'bridge.sock'
    server=codex_bridge._Server(str(path),codex_bridge._Handler)
    worker=Thread(target=lambda:server.serve_forever(poll_interval=.01),daemon=True)
    worker.start()
    try:
        with httpx.Client(transport=httpx.HTTPTransport(uds=str(path)),base_url='http://codex-local',timeout=2) as client:
            response=client.post('/completion',json={'messages':[],'tools':[]})
        assert response.status_code==503
        assert response.json()['error']['code']==('ai_provider_busy' if busy else 'ai_provider_timeout')
        assert response.headers['content-type']=='application/json'
        assert releases==([] if busy else [True])
    finally:
        server.shutdown();server.server_close();worker.join(timeout=2)


def test_rpc_deadline_has_a_controlled_timeout_code(monkeypatch):
    monkeypatch.setattr(codex_bridge.time,'monotonic',lambda:2)
    rpc=codex_bridge._Rpc(SimpleNamespace(stdout=None),1)
    with pytest.raises(codex_bridge.CodexBridgeError) as error:
        rpc.next()
    assert error.value.code=='ai_provider_timeout'
