"""Independent transaction-entry acceptance using synthetic REST and real Chromium."""
import pytest

from test_account_cash_update_qa import browser_wait, cash_browser_document
from test_native_account_history_qa import chromium


def ready(tmp_path, chromium, width=1440, language="en"):
    command, evaluate = chromium
    command("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
    command("Page.navigate", {"url": cash_browser_document(tmp_path, language).as_uri()})
    browser_wait(evaluate, "window.qa?.ready===true")
    evaluate(r'''
qa.txPosts=[];qa.txMode='ok';qa.txReads=0;
qa.instrument={id:'qa-equity',symbol:'QATEST',stock_market:'NASDAQ',asset_class:'EQUITY',instrument_type:'STOCK',location:'USA',currency:'USD',name:'Synthetic equity'};
qa.rows=[{id:'qa-existing',account_db_id:'qa-dollar',security_id:'qa-equity',action:'BUY',symbol:'QATEST',stock_market:'NASDAQ',asset_class:'EQUITY',instrument_type:'STOCK',quantity:7.5,price_input:0,price:0,currency:'USD',trade_date:'2026-11-02',comments:'Existing zero price'}];
api=async(path,options={})=>{
 if(path==='/api/local/manual-securities')return {items:[qa.instrument]};
 if(path.startsWith('/api/local/securities')&&['POST','PUT'].includes(options.method)){
  qa.txPosts.push({path,method:options.method,payload:JSON.parse(options.body)});
  if(qa.txMode==='error'){const error=new Error('synthetic rejected input');error.status=422;throw error;}
  if(qa.txMode==='unknown')throw new Error('synthetic connection interruption');
  const save=()=>{const payload=qa.txPosts.at(-1).payload;const row={...payload,id:options.method==='PUT'?'qa-existing':'qa-created',price_input:Number(payload.price_input),price:Number(payload.price_input),currency:'USD'};qa.rows=[row,...qa.rows.filter(tx=>tx.id!==row.id)];return row;};
  if(qa.txMode==='hold')return await new Promise(resolve=>qa.resolveTx=()=>resolve(save()));
  const result=save();if(qa.txMode==='reload-error')qa.failTxReload=true;return result;
 }
 if(path==='/api/local/securities'){qa.txReads++;if(qa.failTxReload){qa.failTxReload=false;throw new Error('synthetic read failure');}return {items:qa.rows};}
 return {items:[]};
};
loadLocalAccounts=async()=>{refreshLocalAccountSelects();};
loadEquityCompQuotes=async()=>{};
refreshLocalizedFormOptions();refreshLocalAccountSelects();setSecuritiesWorkflow('general');openModal('securitiesModal');
qa.entry=()=>$('securityQuantity').closest('.modal');
qa.new=()=>[...$('securitiesModal').querySelectorAll('button')].find(b=>b.textContent.trim()===t('New transaction'));
''')
    browser_wait(evaluate, "qa.txReads>0&&$('securitiesList').children.length===1")
    return command, evaluate


def key(command, key, code=None, shift=False):
    command("Input.dispatchKeyEvent", {"type": "keyDown", "key": key, "code": code or key, "modifiers": 8 if shift else 0})
    command("Input.dispatchKeyEvent", {"type": "keyUp", "key": key, "code": code or key})


@pytest.mark.parametrize("width,language", [(1440, "en"), (1440, "he"), (390, "en"), (390, "he")])
def test_transaction_popup_open_cancel_layout_keyboard_and_permissions(tmp_path, chromium, width, language):
    command, evaluate = ready(tmp_path, chromium, width, language)
    assert evaluate("qa.entry().id!=='securitiesModal'&&qa.entry().hidden")
    assert evaluate("!!qa.new()")
    assert evaluate("qa.txPosts.length") == 0
    evaluate("qa.new().focus();qa.new().click();")
    browser_wait(evaluate, "!qa.entry().hidden&&qa.entry().contains(document.activeElement)")
    assert evaluate("$('securitiesModal').inert")
    browser_wait(evaluate, "state.transactionEntry.ready")
    assert evaluate("$('transactionEntryTitle').textContent") == ("פעולה חדשה" if language == "he" else "New transaction")
    if language == 'he':
        assert 'Quantity' not in evaluate("$('securityQuantityLabel').textContent")
        assert 'Transaction Date' not in evaluate("$('securityDateLabel').textContent")
        assert 'Free symbol' not in evaluate("$('securityKnownInstrument').options[0].textContent")
    assert evaluate("$('securitiesModal').getAttribute('aria-hidden')") == "true"
    evaluate("$('securityQuantity').value='1234567.1234';$('securityPrice').value='9876543.1234';$('securityDate').value='04/11/2026';$('securityComments').value='Canceled draft';")
    geometry = evaluate("(()=>{let card=qa.entry().querySelector('.modal-card').getBoundingClientRect();return {left:card.left,right:card.right,qty:$('securityQuantity').getBoundingClientRect().width,price:$('securityPrice').getBoundingClientRect().width,overflow:document.documentElement.scrollWidth-innerWidth};})()")
    assert geometry['left'] >= 0 and geometry['right'] <= width and geometry['overflow'] <= 1 and min(geometry['qty'], geometry['price']) >= 140, geometry
    evaluate("qa.controls=[...qa.entry().querySelectorAll('button:not([disabled]),input:not([disabled]),select:not([disabled]),[tabindex=\"0\"]')].filter(x=>x.getClientRects().length);qa.controls.at(-1).focus();")
    key(command, 'Tab')
    assert evaluate("qa.entry().contains(document.activeElement)")
    key(command, 'Escape')
    browser_wait(evaluate, "qa.entry().hidden&&!$('securitiesModal').inert")
    browser_wait(evaluate, "document.activeElement===qa.new()")
    assert evaluate("qa.txPosts.length") == 0
    evaluate("qa.new().click();")
    assert evaluate("[$('securityQuantity').value,$('securityDate').value,$('securityComments').value]") == ['', evaluate("formatDate(todayString())"), '']
    evaluate("closeModal(qa.entry());state.auth.user.role='Viewer';renderCurrentUser();qa.new().click();saveSecurity();")
    assert evaluate("qa.entry().hidden")
    assert evaluate("qa.txPosts.length") == 0
    assert evaluate("qa.errors") == []


def test_transaction_popup_save_once_error_retry_and_zero_price_edit(tmp_path, chromium):
    _, evaluate = ready(tmp_path, chromium)
    evaluate("qa.new().click();")
    browser_wait(evaluate, "state.transactionEntry.ready&&!$('saveSecurity').disabled")
    evaluate("$('securityKnownInstrument').value='qa-equity';$('securityKnownInstrument').dispatchEvent(new Event('change',{bubbles:true}));$('securityQuantity').value='2.5';$('securityPrice').value='123.4567';$('securityDate').value='04/11/2026';$('securityComments').value='Saved note';qa.txMode='error';$('saveSecurity').click();")
    browser_wait(evaluate, "qa.txPosts.length===1&&!$('saveSecurity').disabled")
    assert evaluate("!qa.entry().hidden&&$('securityQuantity').value==='2.5'&&$('securityComments').value==='Saved note'")
    evaluate("qa.txMode='hold';$('saveSecurity').click();$('saveSecurity').click();saveSecurity();")
    browser_wait(evaluate, "qa.txPosts.length===2&&$('saveSecurity').disabled")
    evaluate("closeModal(qa.entry());")
    assert evaluate("qa.entry().hidden") is False
    evaluate("qa.resolveTx();")
    browser_wait(evaluate, "qa.entry().hidden&&!$('securitiesModal').inert&&$('securitiesList').textContent.includes('QATEST')")
    assert evaluate("qa.txPosts.length") == 2
    payload = evaluate("qa.txPosts.at(-1)")
    assert payload['path'] == '/api/local/securities' and payload['method'] == 'POST'
    assert {key:payload['payload'][key] for key in ['account_db_id','security_id','quantity','price_input','trade_date','comments']} == {'account_db_id':'qa-dollar','security_id':'qa-equity','quantity':'2.5','price_input':'123.4567','trade_date':'2026-11-04','comments':'Saved note'}
    evaluate("editSecurityTransaction('qa-existing');")
    browser_wait(evaluate, "!qa.entry().hidden")
    assert evaluate("$('transactionEntryTitle').textContent") == "Edit transaction"
    assert evaluate("$('securityPrice').value") == '0'
    assert evaluate("$('securityDate').value") == '02/11/2026'
    evaluate("qa.txMode='ok';$('securityComments').value='Corrected';$('saveSecurity').click();")
    browser_wait(evaluate, "qa.entry().hidden&&qa.txPosts.length===3")
    assert evaluate("qa.txPosts.at(-1).path") == '/api/local/securities/qa-existing'
    assert evaluate("qa.txPosts.at(-1).method") == 'PUT'
    evaluate("qa.new().click();")
    assert evaluate("state.editingTransactionId") == ''
    assert evaluate("$('securityQuantity').value") == ''
    assert evaluate("qa.errors") == []


def test_catalog_use_opens_entry_with_selected_instrument_and_save_reload_failure(tmp_path, chromium):
    _, evaluate = ready(tmp_path, chromium)
    evaluate("closeModal($('securitiesModal'));openModal('instrumentCatalogModal');")
    browser_wait(evaluate, "!!$('instrumentCatalogModal').querySelector('[data-use-manual-security=\"qa-equity\"]')")
    evaluate("$('instrumentCatalogModal').querySelector('[data-use-manual-security=\"qa-equity\"]').click();")
    browser_wait(evaluate, "!qa.entry().hidden&&$('securityKnownInstrument').value==='qa-equity'")
    assert evaluate("$('securitySymbol').value") == 'QATEST'
    assert evaluate("$('securityMarket').value") == 'NASDAQ'
    assert evaluate("qa.txPosts.length") == 0
    evaluate("$('securityQuantity').value='1';$('securityPrice').value='0';$('securityDate').value='04/11/2026';qa.txMode='reload-error';$('saveSecurity').click();")
    browser_wait(evaluate, "qa.txPosts.length===1&&qa.entry().hidden")
    browser_wait(evaluate, "$('securitiesListStatus').textContent.includes('Transaction saved.')")
    assert evaluate("qa.txPosts.length") == 1
    assert evaluate("$('securityPrice').value") == ''
    assert evaluate("qa.errors") == []


def test_slow_parent_load_does_not_overwrite_open_entry_or_focus(tmp_path, chromium):
    _, evaluate = ready(tmp_path, chromium)
    evaluate("closeModal($('securitiesModal'));qa.originalApi=api;qa.holdFirst=true;api=async(path,options={})=>{if(path==='/api/local/manual-securities'&&qa.holdFirst){qa.holdFirst=false;return await new Promise(resolve=>qa.resolveRead=()=>resolve({items:[qa.instrument]}));}return qa.originalApi(path,options);};openModal('securitiesModal');qa.new().click();")
    browser_wait(evaluate, "state.transactionEntry.ready&&document.activeElement.id==='securityAccount'")
    evaluate("$('securitySymbol').value='DRAFT';$('securityQuantity').value='2.75';$('securityDate').value='03/11/2026';$('securityComments').value='Still typing';$('securityQuantity').focus();qa.resolveRead();")
    browser_wait(evaluate, "qa.txReads===2")
    assert evaluate("[$('securitySymbol').value,$('securityQuantity').value,$('securityDate').value,$('securityComments').value]") == ['DRAFT','2.75','03/11/2026','Still typing']
    assert evaluate("document.activeElement.id") == 'securityQuantity'
    assert evaluate("qa.txPosts.length") == 0
    assert evaluate("qa.errors") == []


def test_entry_after_employee_workflow_uses_general_transaction_fields(tmp_path, chromium):
    _, evaluate = ready(tmp_path, chromium)
    evaluate("setSecuritiesWorkflow('employee-options');closeModal($('securitiesModal'));editSecurityTransaction('qa-existing');")
    browser_wait(evaluate, "state.transactionEntry.ready")
    assert evaluate("$('securitySymbol').getClientRects().length>0")
    assert evaluate("$('securityAction').disabled") is False
    assert evaluate("$('securityAccount').value") == 'qa-dollar'
    assert evaluate("$('securityPriceField').hidden") is False


def test_session_change_resets_transaction_parent_and_draft(tmp_path, chromium):
    _, evaluate = ready(tmp_path, chromium)
    evaluate("qa.new().focus();qa.new().click();")
    browser_wait(evaluate, "state.transactionEntry.ready")
    evaluate("$('securitySymbol').value='PRIVATE_DRAFT';$('securityComments').value='Old owner';showLogin();")
    assert evaluate("qa.entry().hidden")
    assert evaluate("$('securitiesModal').inert") is False
    assert evaluate("$('securityComments').value") == ''
    evaluate("setAuthenticatedSession({user:{id:'new-owner',username:'new',role:'Operator'},csrf_token:'synthetic'});hideAuthOverlay();openModal('securitiesModal');qa.new().click();")
    browser_wait(evaluate, "state.transactionEntry.ready")
    assert evaluate("$('securityComments').value") == ''


def test_previous_session_pending_save_cannot_close_next_owner_entry(tmp_path, chromium):
    _, evaluate = ready(tmp_path, chromium)
    evaluate("qa.new().focus();qa.new().click();")
    browser_wait(evaluate, "state.transactionEntry.ready")
    evaluate("$('securitySymbol').value='QATEST';$('securityMarket').value='NASDAQ';$('securityQuantity').value='1';$('securityPrice').value='2';qa.txMode='hold';$('saveSecurity').click();")
    browser_wait(evaluate, "qa.txPosts.length===1")
    evaluate("showLogin();setAuthenticatedSession({user:{id:'new-owner',username:'new',role:'Operator'},csrf_token:'synthetic'});hideAuthOverlay();openModal('securitiesModal');qa.new().focus();qa.new().click();")
    browser_wait(evaluate, "!qa.entry().hidden&&state.transactionEntry.ready&&!$('saveSecurity').disabled")
    evaluate("$('securityComments').value='New owner draft';qa.resolveTx();")
    browser_wait(evaluate, "qa.rows.some(row=>row.id==='qa-created')")
    assert evaluate("qa.entry().hidden") is False
    assert evaluate("$('securityComments').value") == 'New owner draft'
    assert evaluate("qa.txPosts.length") == 1
    assert evaluate("qa.errors") == []


def test_loading_failure_can_close_and_reopen_without_posting(tmp_path, chromium):
    _, evaluate = ready(tmp_path, chromium)
    evaluate("qa.originalApi=api;api=async(path,options={})=>{if(path==='/api/local/manual-securities')throw new Error('synthetic load failure');return qa.originalApi(path,options);};qa.new().focus();qa.new().click();")
    browser_wait(evaluate, "$('securityStatus').textContent.includes('Could not load transaction details')")
    assert evaluate("$('saveSecurity').disabled")
    assert evaluate("qa.txPosts.length") == 0
    evaluate("qa.entry().querySelector('button[data-close]').click();api=qa.originalApi;qa.new().focus();qa.new().click();")
    browser_wait(evaluate, "state.transactionEntry.ready&&!$('saveSecurity').disabled")
    assert evaluate("$('securityComments').value") == ''
    assert evaluate("qa.txPosts.length") == 0
    assert evaluate("qa.errors") == []


def test_missing_edit_target_cannot_be_saved_as_new_transaction(tmp_path, chromium):
    _, evaluate = ready(tmp_path, chromium)
    evaluate("editSecurityTransaction('deleted-target');")
    browser_wait(evaluate, "!state.transactionEntry.loading")
    assert evaluate("$('saveSecurity').disabled")
    assert evaluate("$('securityStatus').textContent.length>0")
    evaluate("saveSecurity();")
    assert evaluate("qa.txPosts.length") == 0


def test_unknown_save_outcome_blocks_duplicate_retry_and_keeps_input(tmp_path, chromium):
    _, evaluate = ready(tmp_path, chromium)
    evaluate("qa.new().focus();qa.new().click();")
    browser_wait(evaluate, "state.transactionEntry.ready")
    evaluate("$('securitySymbol').value='QATEST';$('securityMarket').value='NASDAQ';$('securityQuantity').value='1';$('securityPrice').value='2';$('securityComments').value='Check before repeating';qa.txMode='unknown';$('saveSecurity').click();")
    browser_wait(evaluate, "qa.txPosts.length===1&&!state.transactionEntry.saving")
    assert evaluate("$('saveSecurity').disabled")
    assert evaluate("qa.entry().hidden") is False
    assert evaluate("$('securityComments').value") == 'Check before repeating'
    assert 'check' in evaluate("$('securityStatus').textContent").lower()
    evaluate("saveSecurity();$('saveSecurity').click();")
    assert evaluate("qa.txPosts.length") == 1


def test_direct_owner_replacement_resets_entry_and_parent(tmp_path, chromium):
    _, evaluate = ready(tmp_path, chromium)
    evaluate("qa.new().focus();qa.new().click();")
    browser_wait(evaluate, "state.transactionEntry.ready")
    evaluate("$('securityComments').value='Private old-owner draft';setAuthenticatedSession({user:{id:'replacement-owner',username:'new',role:'Operator'},csrf_token:'synthetic'});")
    assert evaluate("qa.entry().hidden")
    assert evaluate("$('securityComments').value") == ''
    assert evaluate("$('securitiesModal').inert") is False
    assert evaluate("qa.txPosts.length") == 0
