"""Independent real-page browser checks with synthetic saved transactions only."""
import base64

import pytest

from test_account_cash_update_qa import browser_wait, cash_browser_document
from test_native_account_history_qa import chromium


def transaction_document(tmp_path, language):
    page = cash_browser_document(tmp_path, language)
    script = tmp_path / 'cash-app.js'
    with script.open('a') as stream:
        stream.write(r'''
qa.calls=[];qa.writes=[];
const raw=(id,symbol,action,quantity,price,trade_date,extra={})=>({id,symbol,action,quantity,price,price_input:price,trade_date,
 account_db_id:'qa-dollar',account_id:'QA1',management_company:'Synthetic Broker',stock_market:'NYSE',asset_class:'EQUITY',
 instrument_type:'STOCK',currency:'USD',comments:'',created_at:trade_date+'T12:00:00Z',...extra});
qa.records=[
 raw('bsm','BSM','DIVIDEND',615,.2625,'2026-11-03',{security_name:'Black Stone Minerals',comments:'Quarterly distribution'}),
 raw('sar-a','SAR','DIVIDEND',101,.1875,'2026-11-03'),
 raw('sar-b','SAR','DIVIDEND',57,.1875,'2026-11-03',{account_db_id:'qa-second',account_id:'QA2'}),
 raw('tase','1191844','BUY',415000,1.0896,'2026-10-31',{price_input:108.96,secondary_symbol:'TASE-TEST',currency:'ILS',stock_market:'TASE',security_name:'Synthetic local bond'}),
 raw('unb','UNB','DIVIDEND',52,.27,'2026-10-02'),
 raw('bond','88059ESH8','REMOVE',8000,.98,'2026-11-02',{comments:'Imported source SELL · synthetic redemption',instrument_type:'BOND',asset_class:'BOND',secondary_symbol:'US88059ESH81',security_name:'Synthetic bond'}),
 raw('two','Two','BUY',2,2,'2026-09-30'),
 raw('ten','Ten','BUY',10,10,'2026-10-01'),
 raw('zero','Zero','BUY',0,0,'2026-10-01'),
 raw('missing','Missing','BUY',null,null,'',{price_input:null}),
 raw('cash','CASH','CASH_IN',1000,1,'2026-11-09'),
 raw('option','OPTION-ONLY','ADD',50,0,'2026-11-10',{instrument_type:'EMPLOYEE_STOCK_OPTION',transition_id:'synthetic-lifecycle',company_name:'Synthetic option'})
];
state.localAccounts.push({id:'qa-second',username:'Synthetic Second',account_id:'QA2',type:'Investment',location:'USA',currency:'USD',persons:[]});
state.items=[];state.localTransactions=structuredClone(qa.records);
api=async(path,options={})=>{qa.calls.push({path,method:options.method||'GET'});
 if(options.method&&options.method!=='GET')qa.writes.push({path,method:options.method});
 if(options.method==='DELETE'){qa.records=qa.records.filter(tx=>tx.id!==path.split('/').pop());return {deleted:true};}
 if(options.method==='POST'){const payload=JSON.parse(options.body);qa.records.push(raw('new-sar','SAR','DIVIDEND',7,.1875,'2026-11-03',payload));return {id:'new-sar'};}
 if(path==='/api/local/securities')return {items:structuredClone(qa.records)};
 return {items:[]};};
loadManualSecurities=async()=>{};loadEquityCompQuotes=async()=>{};
state.securitiesWorkflow='general';setSecuritiesWorkflow('general');
loadLocalSecurities().then(()=>{openModal('securitiesModal');qa.transactionsReady=true;});
''')
    return page


def ready(tmp_path, chromium, language='en', width=1440):
    command, evaluate = chromium
    command('Emulation.setDeviceMetricsOverride', dict(width=width,height=1000,deviceScaleFactor=1,mobile=False))
    command('Page.navigate', {'url': transaction_document(tmp_path, language).as_uri()})
    browser_wait(evaluate, 'window.qa?.transactionsReady===true')
    assert evaluate('qa.errors') == []
    return command, evaluate


def change(evaluate, element, value, event='change'):
    import json
    evaluate(f"$({json.dumps(element)}).value={json.dumps(value)};$({json.dumps(element)}).dispatchEvent(new Event({json.dumps(event)},{{bubbles:true}}));")


def ids(evaluate):
    return evaluate("[...$('securitiesList').querySelectorAll('[data-transaction-id]')].map(n=>n.dataset.transactionId)")


@pytest.mark.parametrize('language,width', [('en',1440),('he',1440),('en',390),('he',390)])
def test_filters_dates_effective_import_actions_and_responsive_keyboard(tmp_path, chromium, language, width):
    command, evaluate = ready(tmp_path, chromium, language, width)
    baseline = ids(evaluate)
    assert 'cash' not in baseline
    assert baseline[0] == 'option'
    assert baseline[-1] == 'missing'
    assert len(baseline) == 11
    assert '${' not in evaluate("$('securitiesList').innerText")
    assert '02/11/2026' in evaluate("$('securitiesList').innerText")
    bond_text = evaluate("document.querySelector('[data-edit-security=bond]').closest('.stack-item').innerText")
    assert ('Sell' if language == 'en' else 'מכירה') in bond_text
    assert '8000' in bond_text.replace(',', '')
    assert '0.98' in bond_text
    # Text search reaches symbol, alternate identity, name and comments without requests.
    start_calls = evaluate('qa.calls.length')
    before = evaluate('JSON.stringify(state.localTransactions)')
    for query, expected in [('88059esh8',['bond']),('US88059ESH81',['bond']),
                            ('black stone',['bsm']),('quarterly distribution',['bsm'])]:
        change(evaluate, 'transactionFilterQuery', query, 'input')
        assert ids(evaluate) == expected
    change(evaluate, 'transactionFilterQuery', '', 'input')
    change(evaluate, 'transactionFilterAccount', 'id:qa-dollar')
    change(evaluate, 'transactionFilterAction', 'DIVIDEND')
    change(evaluate, 'transactionFilterFrom', '01/11/2026')
    change(evaluate, 'transactionFilterTo', '03/11/2026')
    assert set(ids(evaluate)) == {'bsm','sar-a'}
    assert '2' in evaluate("$('transactionFilterStatus').textContent")
    # Bounds are inclusive and invalid dates retain last valid result.
    change(evaluate, 'transactionFilterTo', '02/11/2026')
    assert ids(evaluate) == []
    assert ('No transactions match' if language == 'en' else 'אין') in evaluate("$('securitiesList').innerText")
    change(evaluate, 'transactionFilterTo', '31/02/2026')
    assert ids(evaluate) == []
    assert evaluate("$('transactionFilterStatus').textContent.trim().length>0")
    assert evaluate("$('transactionFilterTo').value") == '31/02/2026'
    evaluate("$('resetTransactionFilters').click()")
    assert ids(evaluate) == baseline
    assert evaluate("$('transactionFilterFrom').value===''&&$('transactionFilterTo').value===''")
    for action in ['SELL','REMOVE']:
        change(evaluate, 'transactionFilterAction', action)
        assert ids(evaluate) == ['bond']
    # Actual keyboard activation of Reset and native select preserve focus.
    evaluate("$('resetTransactionFilters').scrollIntoView({block:'center'});$('resetTransactionFilters').focus()")
    command('Input.dispatchKeyEvent',{'type':'keyDown','key':'Enter','code':'Enter','windowsVirtualKeyCode':13,'text':'\r'})
    command('Input.dispatchKeyEvent',{'type':'keyUp','key':'Enter','code':'Enter','windowsVirtualKeyCode':13})
    assert ids(evaluate) == baseline
    assert evaluate('document.activeElement.id') == 'resetTransactionFilters'
    evaluate("$('transactionFilterAction').focus()")
    for key,code in [('End',35),('Home',36)]:
        command('Input.dispatchKeyEvent',{'type':'keyDown','key':key,'code':key,'windowsVirtualKeyCode':code})
        command('Input.dispatchKeyEvent',{'type':'keyUp','key':key,'code':key,'windowsVirtualKeyCode':code})
        assert ids(evaluate)==([] if key=='End' else baseline)
        assert evaluate('document.activeElement.id')=='transactionFilterAction'
    assert evaluate('qa.calls.length') == start_calls
    assert evaluate('qa.writes') == []
    assert evaluate('JSON.stringify(state.localTransactions)') == before
    bounds = evaluate("[...$('transactionListFilters').querySelectorAll('input,select,button')].map(n=>{const r=n.getBoundingClientRect();return {id:n.id,left:r.left,right:r.right,width:r.width,height:r.height};})")
    assert all(b['left']>=0 and b['right']<=width and b['width']>=80 and b['height']>=24 for b in bounds), bounds
    assert evaluate('innerWidth') == width
    assert evaluate("document.documentElement.scrollWidth<=innerWidth")
    row_bounds=evaluate("[...$('securitiesList').querySelectorAll('[data-transaction-id] > b,[data-transaction-id] > span')].map(n=>({text:n.textContent,width:n.clientWidth,scroll:n.scrollWidth})).filter(n=>n.width<80||n.scroll>n.width+1)")
    assert row_bounds==[], row_bounds
    overlap=evaluate("[...$('securitiesList').querySelectorAll('[data-transaction-id]')].flatMap(row=>{const nodes=[...row.children].filter(n=>n.tagName==='B'||n.tagName==='SPAN');return nodes.flatMap((a,i)=>nodes.slice(i+1).flatMap(b=>{const x=a.getBoundingClientRect(),y=b.getBoundingClientRect();return x.left<y.right-1&&x.right>y.left+1&&x.top<y.bottom-1&&x.bottom>y.top+1?[row.dataset.transactionId]:[]}));})")
    assert overlap==[], overlap
    if language == 'he':
        visible = evaluate("$('securitiesSubtitle').innerText+' '+$('savedTransactionsLabel').innerText+' '+$('transactionListFilters').innerText+' '+$('transactionFilterStatus').innerText+' '+$('securitiesList').innerText")
        for operational in ['Saved transactions','Choose a defined instrument and record its transaction in an account.','Sort by','Ascending','Descending','Sell','Remove','Edit','Delete','Cash ','No cash movement','Lifecycle transaction','read-only']:
            assert operational not in visible, operational
    screenshot=command('Page.captureScreenshot',{'format':'png'})
    (tmp_path/f'transactions-{language}-{width}.png').write_bytes(base64.b64decode(screenshot['data']))
    assert evaluate('qa.errors') == []


@pytest.mark.parametrize('language',['en','he'])
def test_sort_raw_numeric_text_dates_stable_missing_last_and_persistent_state(tmp_path, chromium, language):
    _, evaluate = ready(tmp_path, chromium, language)
    change(evaluate,'transactionSortBy','quantity')
    change(evaluate,'transactionSortDirection','asc')
    order=ids(evaluate)
    assert order == ['zero','two','ten','option','unb','sar-b','sar-a','bsm','bond','tase','missing']
    change(evaluate,'transactionSortDirection','desc')
    assert ids(evaluate) == ['tase','bond','bsm','sar-a','sar-b','unb','option','ten','two','zero','missing']
    change(evaluate,'transactionSortBy','date')
    change(evaluate,'transactionSortDirection','asc')
    order=ids(evaluate)
    assert order.index('two')<order.index('ten')<order.index('unb')<order.index('tase')<order.index('bond')<order.index('bsm')
    assert order[-1]=='missing'
    # Sorting text uses a natural comparison, stable equal date/creation rows.
    change(evaluate,'transactionSortBy','security')
    order=ids(evaluate)
    assert order.index('bsm')<order.index('sar-a')<order.index('ten')<order.index('two')
    evaluate('renderLocalTransactions();renderLocalTransactions();')
    assert ids(evaluate)==order
    # Preserve filters, raw invalid date draft and last valid rows through source refresh.
    change(evaluate,'transactionFilterQuery','SAR','input')
    change(evaluate,'transactionFilterFrom','01/11/2026')
    change(evaluate,'transactionFilterTo','broken')
    previous=ids(evaluate)
    evaluate('loadLocalSecurities()')
    assert ids(evaluate)==previous
    assert evaluate("$('transactionFilterQuery').value")=='SAR'
    assert evaluate("$('transactionFilterTo').value")=='broken'
    evaluate("closeModal($('securitiesModal'));openModal('securitiesModal');")
    assert ids(evaluate)==previous
    assert evaluate("$('transactionFilterTo').value")=='broken'
    evaluate("state.language=state.language==='en'?'he':'en';applyLanguage();")
    assert ids(evaluate)==previous
    assert evaluate("$('transactionFilterQuery').value")=='SAR'
    assert evaluate("$('transactionFilterTo').value")=='broken'
    assert evaluate('qa.writes')==[]
    assert evaluate('qa.errors')==[]


def test_viewer_filters_and_employee_workflow_isolation_and_session_reset(tmp_path, chromium):
    _, evaluate = ready(tmp_path, chromium)
    change(evaluate,'transactionFilterQuery','no-such-record','input')
    assert ids(evaluate)==[]
    evaluate("setSecuritiesWorkflow('employee-options');renderLocalTransactions();")
    assert evaluate("$('transactionListFilters').hidden")
    assert evaluate("!$('transactionFilterStatus').checkVisibility()")
    assert 'Synthetic option' in evaluate("$('securitiesList').textContent")
    evaluate("setSecuritiesWorkflow('general');renderLocalTransactions();")
    assert ids(evaluate)==[]
    evaluate("state.auth.user.role='Viewer';applyRolePermissions();$('resetTransactionFilters').click();")
    assert evaluate("$('transactionFilterQuery').disabled") is False
    assert evaluate("$('transactionSortBy').disabled") is False
    assert evaluate("$('resetTransactionFilters').disabled") is False
    assert evaluate("[...$('securitiesList').querySelectorAll('[data-edit-security],[data-delete-security]')].every(n=>n.disabled)")
    change(evaluate,'transactionFilterQuery','88059ESH8','input')
    assert '88059ESH8' in evaluate("$('securitiesList').textContent")
    assert evaluate('qa.writes')==[]
    evaluate("setAuthenticatedSession({user:{id:'qa-other',username:'other',role:'Viewer'},csrf_token:'synthetic'});renderLocalTransactions();")
    assert evaluate("$('transactionFilterQuery').value")==''
    change(evaluate,'transactionFilterQuery','SAR','input')
    evaluate('showLogin()')
    assert evaluate("$('transactionFilterQuery').value")==''
    assert evaluate('qa.errors')==[]


def test_actual_save_and_delete_handlers_preserve_filter_sort_and_invalid_date_draft(tmp_path, chromium):
    _,evaluate=ready(tmp_path,chromium)
    change(evaluate,'transactionFilterQuery','SAR','input')
    change(evaluate,'transactionSortBy','quantity')
    change(evaluate,'transactionSortDirection','asc')
    change(evaluate,'transactionFilterTo','31/02/2026')
    assert ids(evaluate)==['sar-b','sar-a']
    # Exercise the production delegated delete handler against the synthetic transport.
    evaluate("document.querySelector('[data-delete-security=sar-a]').focus();document.querySelector('[data-delete-security=sar-a]').click()")
    browser_wait(evaluate,"!state.localTransactions.some(tx=>tx.id==='sar-a')")
    assert ids(evaluate)==['sar-b']
    assert evaluate('document.activeElement.id')=='resetTransactionFilters'
    evaluate("document.querySelector('[data-edit-security=sar-b]').focus();loadLocalSecurities()")
    assert evaluate("document.activeElement.dataset.editSecurity")=='sar-b'
    assert evaluate("$('transactionFilterQuery').value")=='SAR'
    assert evaluate("$('transactionFilterTo').value")=='31/02/2026'
    assert evaluate("$('transactionSortDirection').value")=='asc'
    # A confirmed save refreshes the same saved-list renderer without discarding criteria.
    evaluate("state.transactionEntry={version:1,loading:false,saving:false,ready:true};openModal('transactionEntryModal',$('newSecurityTransaction'));state.editingTransactionId='';$('securitySymbol').value='SAR';$('securityQuantity').value='7';$('securityPrice').value='.1875';$('securityAction').value='DIVIDEND';")
    evaluate('saveSecurity()')
    browser_wait(evaluate,"state.localTransactions.some(tx=>tx.id==='new-sar')")
    assert 'new-sar' in ids(evaluate)
    browser_wait(evaluate,"document.activeElement.id==='newSecurityTransaction'")
    assert evaluate("$('transactionFilterQuery').value")=='SAR'
    assert evaluate("$('transactionFilterTo').value")=='31/02/2026'
    assert evaluate("$('transactionSortBy').value")=='quantity'
    assert evaluate("qa.writes.map(r=>r.method)")==['DELETE','POST']
    assert evaluate('qa.errors')==[]


def test_removed_account_choice_stays_visible_until_explicit_reset(tmp_path, chromium):
    _,evaluate=ready(tmp_path,chromium)
    change(evaluate,'transactionFilterAccount','id:qa-second')
    assert ids(evaluate)==['sar-b']
    label=evaluate("$('transactionFilterAccount').selectedOptions[0].textContent")
    evaluate("qa.records=qa.records.filter(tx=>tx.account_db_id!=='qa-second');loadLocalSecurities()")
    assert ids(evaluate)==[]
    assert evaluate("$('transactionFilterAccount').value")=='id:qa-second'
    assert evaluate("$('transactionFilterAccount').selectedOptions[0].textContent")==label
    evaluate("$('resetTransactionFilters').click()")
    assert len(ids(evaluate))==10
    assert evaluate('qa.writes')==[]
    assert evaluate('qa.errors')==[]


@pytest.mark.parametrize('language',['en','he'])
def test_display_preserves_native_normalized_units_and_unknown_amounts(tmp_path,chromium,language):
    _,evaluate=ready(tmp_path,chromium,language)
    text=evaluate("document.querySelector('[data-transaction-id=tase]').innerText")
    assert '415,000' in text and '108.96' in text and '1.0896' in text
    missing=evaluate("document.querySelector('[data-transaction-id=missing]').innerText")
    assert ('Not available' if language=='en' else 'לא זמין') in missing
    assert ('Cash movement unavailable' if language=='en' else 'לא זמין') in missing
    zero=evaluate("document.querySelector('[data-transaction-id=zero]').innerText")
    assert '0 @ 0' in zero
    assert ('Not available' if language=='en' else 'לא זמין') not in zero
    for tx,quantity,price in [('bsm',615,.2625),('sar-a',101,.1875),('sar-b',57,.1875),('unb',52,.27)]:
        text=evaluate(f"document.querySelector('[data-transaction-id={tx}]').innerText")
        assert str(quantity) in text and str(price) in text
    assert evaluate('qa.errors')==[]
