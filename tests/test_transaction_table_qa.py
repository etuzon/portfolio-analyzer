"""Independent acceptance checks for the saved transaction table.

The real HTML, CSS and event handlers run with synthetic read-only transport;
these tests never open the runtime portfolio or modify an import source.
"""
import pytest

from test_native_account_history_qa import chromium
from test_saved_transactions_qa import change, ids, ready, sort


@pytest.mark.parametrize('language', ['en', 'he'])
def test_semantic_table_headers_keyboard_sort_and_invalid_date_recovery(tmp_path, chromium, language):
    command, evaluate = ready(tmp_path, chromium, language)
    assert evaluate("$('savedTransactionsTable').tagName") == 'TABLE'
    assert evaluate("$('savedTransactionsTable').tHead.rows.length") == 1
    assert evaluate("$('savedTransactionsTable').tBodies.length") == 1
    assert evaluate("[...$('savedTransactionsTable').tBodies[0].rows].every(r=>r.matches('tr[data-transaction-id]')&&r.cells.length===8)")
    assert evaluate("document.querySelectorAll('#transactionSortBy,#transactionSortDirection').length") == 0
    assert evaluate("[...$('savedTransactionsTable').querySelectorAll('thead th')].every(th=>th.scope==='col')")
    assert evaluate("$('savedTransactionsTable').querySelectorAll('thead button[data-transaction-sort]').length") == 5
    assert evaluate("[...$('savedTransactionsTable').querySelectorAll('th,td')].every(cell=>getComputedStyle(cell).display==='table-cell')")
    assert evaluate("document.querySelector('[data-transaction-sort=date]').closest('th').getAttribute('aria-sort')") == 'descending'
    initial_calls = evaluate('qa.calls.length')
    initial_ledger = evaluate('JSON.stringify(state.localTransactions)')
    # Enter activates a real header button and preserves keyboard focus on rerender.
    evaluate("document.querySelector('[data-transaction-sort=quantity]').scrollIntoView({block:'center'});document.querySelector('[data-transaction-sort=quantity]').focus()")
    for key, code, expected in [('Enter',13,'descending'),(' ',32,'ascending')]:
        command('Input.dispatchKeyEvent', {'type':'keyDown','key':key,'code':'Enter' if code==13 else 'Space','windowsVirtualKeyCode':code,'text':'\r' if code==13 else ' '})
        command('Input.dispatchKeyEvent', {'type':'keyUp','key':key,'code':'Enter' if code==13 else 'Space','windowsVirtualKeyCode':code})
        assert evaluate("document.activeElement.dataset.transactionSort") == 'quantity'
        assert evaluate("document.activeElement.closest('th').getAttribute('aria-sort')") == expected
    assert ids(evaluate)[0] == 'zero'
    assert ids(evaluate)[-1] == 'missing'
    # A malformed draft keeps the last valid membership, while header sorting
    # still changes order. Correcting it applies the inclusive date bounds.
    change(evaluate, 'transactionFilterQuery', 'SAR', 'input')
    change(evaluate, 'transactionFilterFrom', '03/11/2026')
    change(evaluate, 'transactionFilterTo', '03/11/2026')
    assert ids(evaluate) == ['sar-b', 'sar-a']
    change(evaluate, 'transactionFilterTo', '31/02/2026')
    sort(evaluate, 'quantity', 'desc')
    assert ids(evaluate) == ['sar-a', 'sar-b']
    assert evaluate("$('transactionFilterTo').getAttribute('aria-invalid')") == 'true'
    assert evaluate("$('transactionFilterTo').value") == '31/02/2026'
    sort(evaluate, 'quantity', 'asc')
    assert ids(evaluate) == ['sar-b', 'sar-a']
    change(evaluate, 'transactionFilterTo', '02/11/2026')
    assert ids(evaluate) == ['sar-b', 'sar-a']  # Reversed range also retains valid membership.
    change(evaluate, 'transactionFilterFrom', '01/11/2026')
    assert ids(evaluate) == []
    evaluate("$('resetTransactionFilters').click()")
    assert ids(evaluate)[0] == 'option'
    assert evaluate("document.querySelector('[data-transaction-sort=date]').closest('th').getAttribute('aria-sort')") == 'descending'
    assert evaluate('qa.calls.length') == initial_calls
    assert evaluate('qa.writes') == []
    assert evaluate('JSON.stringify(state.localTransactions)') == initial_ledger
    assert evaluate('qa.errors') == []


@pytest.mark.parametrize('language,width', [('en',1440),('he',1440),('en',390),('he',390)])
def test_content_sized_filters_scroll_containment_details_and_action_reachability(tmp_path, chromium, language, width):
    command, evaluate = ready(tmp_path, chromium, language, width)
    widths = evaluate("Object.fromEntries(['transactionFilterAccount','transactionFilterAction','transactionFilterFrom','transactionFilterTo','transactionFilterQuery'].map(id=>[id,$(id).getBoundingClientRect().width]))")
    assert 120 <= widths['transactionFilterFrom'] <= 170, widths
    assert 120 <= widths['transactionFilterTo'] <= 170, widths
    assert 130 <= widths['transactionFilterAction'] <= 220, widths
    if width == 1440:
        assert widths['transactionFilterAccount'] <= 320, widths
        assert widths['transactionFilterQuery'] >= widths['transactionFilterAction'], widths
    for field in ['transactionFilterFrom','transactionFilterTo']:
        change(evaluate, field, '03/11/2026')
        assert evaluate(f"$('{field}').scrollWidth<=$('{field}').clientWidth+1")
    evaluate("$('resetTransactionFilters').click()")
    assert evaluate("$('securitiesList').tabIndex") == 0
    assert evaluate("['auto','scroll'].includes(getComputedStyle($('securitiesList')).overflowX)")
    if width == 390:
        assert evaluate("$('securitiesList').scrollWidth>$('securitiesList').clientWidth")
    assert evaluate("document.documentElement.scrollWidth<=innerWidth")
    # Keyboard focus scrolls the actual table container to offscreen actions.
    evaluate("document.querySelector('[data-edit-security=bond]').focus()")
    assert evaluate("document.activeElement.dataset.editSecurity") == 'bond'
    assert evaluate("(()=>{const r=document.activeElement.getBoundingClientRect(),s=$('securitiesList').getBoundingClientRect();return r.left>=s.left-1&&r.right<=s.right+1;})()")
    # Imported SELL remains a noncash REMOVE in storage and display.
    bond = evaluate("document.querySelector('[data-transaction-id=bond]').innerText")
    assert ('Sell' if language=='en' else 'מכירה') in bond
    assert ('No cash movement' if language=='en' else 'ללא תנועת מזומן') in bond
    assert evaluate("state.localTransactions.find(tx=>tx.id==='bond').action") == 'REMOVE'
    assert evaluate("document.querySelector('[data-transaction-id=option]').querySelectorAll('[data-edit-security],[data-delete-security]').length") == 0
    details = evaluate("document.querySelector('[data-transaction-id=bond] details')!==null")
    assert details
    evaluate("document.querySelector('[data-transaction-id=bond] summary').focus()")
    command('Input.dispatchKeyEvent', {'type':'keyDown','key':'Enter','code':'Enter','windowsVirtualKeyCode':13,'text':'\r'})
    command('Input.dispatchKeyEvent', {'type':'keyUp','key':'Enter','code':'Enter','windowsVirtualKeyCode':13})
    assert evaluate("document.querySelector('[data-transaction-id=bond] details').open")
    metadata = evaluate("document.querySelector('[data-transaction-id=bond] details').innerText")
    for value in ['Imported source SELL', 'synthetic redemption']:
        assert value in metadata, metadata
    expanded_row = evaluate("document.querySelector('[data-transaction-id=bond]').innerText")
    assert 'US88059ESH81' in expanded_row and 'Synthetic bond' in expanded_row
    assert evaluate('qa.writes') == []
    assert evaluate('qa.errors') == []


@pytest.mark.parametrize('language', ['en', 'he'])
def test_existing_instrument_metadata_survives_the_table_and_localized_details(tmp_path, chromium, language):
    _, evaluate = ready(tmp_path, chromium, language)
    evaluate("""
Object.assign(state.localTransactions.find(tx=>tx.id==='two'), {
 option_type:'CALL',grant_id:'synthetic-grant-7',expiration_date:'2027-01-02',
 maturity_date:'2030-04-05',vest_date:'2026-12-01',strike_price:12.5,purchase_price:.6,
 comments:'Synthetic metadata <img src=x onerror=alert(1)>'
});renderLocalTransactions();document.querySelector('[data-transaction-id=two] summary').click();
""")
    text = evaluate("document.querySelector('[data-transaction-id=two] details').innerText")
    for value in ['CALL', 'synthetic-grant-7', '02/01/2027', '05/04/2030', '01/12/2026', '12.5', '0.6', 'Synthetic metadata <img']:
        assert value in text, text
    assert evaluate("document.querySelector('[data-transaction-id=two] img')") is None
    if language == 'he':
        for label in ['Stock market', 'Asset class', 'Instrument type', 'Option type', 'Currency', 'Comments', 'Purchase price', 'Strike price', ' price']:
            assert label not in text
    assert evaluate('qa.writes') == []
    assert evaluate('qa.errors') == []


@pytest.mark.parametrize('language', ['en', 'he'])
def test_account_and_localized_action_headers_order_visible_records(tmp_path, chromium, language):
    _, evaluate = ready(tmp_path, chromium, language)
    sort(evaluate, 'account')
    assert evaluate("document.querySelector('[data-transaction-sort=account]').closest('th').getAttribute('aria-sort')") == 'ascending'
    assert ids(evaluate)[-1] == 'sar-b'  # The only QA2 account; every other row is QA1.
    sort(evaluate, 'account')
    assert ids(evaluate)[0] == 'sar-b'
    sort(evaluate, 'action')
    labels = evaluate("[...$('savedTransactionsTable').tBodies[0].rows].map(r=>r.cells[1].innerText)")
    # Group order derives from visible EN/HE action wording, including the
    # imported REMOVE whose disclosed action is Sell.
    distinct = list(dict.fromkeys(labels))
    assert distinct == (['Add','Buy','Dividend','Sell'] if language=='en' else ['דיבידנד','הוספה','מכירה','קנייה'])
    sort(evaluate, 'action')
    descending = evaluate("[...$('savedTransactionsTable').tBodies[0].rows].map(r=>r.cells[1].innerText)")
    assert list(dict.fromkeys(descending)) == distinct[::-1]
    assert evaluate('qa.writes') == []
    assert evaluate('qa.errors') == []


@pytest.mark.parametrize('language', ['en', 'he'])
def test_malformed_saved_date_stays_missing_last_and_does_not_leak_raw_format(tmp_path, chromium, language):
    _, evaluate = ready(tmp_path, chromium, language)
    evaluate("state.localTransactions.find(tx=>tx.id==='missing').trade_date='2026-02-31';renderLocalTransactions();")
    expected = 'Not available' if language=='en' else 'לא זמין'
    assert evaluate("document.querySelector('[data-transaction-id=missing]').cells[0].innerText") == expected
    assert ids(evaluate)[-1] == 'missing'
    sort(evaluate, 'date', 'asc')
    assert ids(evaluate)[-1] == 'missing'
    assert '2026-02-31' not in evaluate("$('securitiesList').innerText")
    assert evaluate('qa.writes') == []
    assert evaluate('qa.errors') == []


def test_hebrew_phone_date_remains_visible_when_vertical_scrollbar_appears_and_disappears(tmp_path, chromium):
    """RTL content must stay at the viewport edge as the result height changes."""
    _, evaluate = ready(tmp_path, chromium, 'he', 390)

    def date_is_inside_viewport():
        bounds = evaluate("""(()=>{
 const region=$('securitiesList'),date=region.querySelector('tbody tr[data-transaction-id] .transaction-date bdi');
 const r=region.getBoundingClientRect(),d=date.getBoundingClientRect();
 return {left:r.left,right:r.right,dateLeft:d.left,dateRight:d.right,scrollLeft:region.scrollLeft,
         vertical:region.scrollHeight>region.clientHeight};
})()""")
        assert bounds['dateLeft'] >= bounds['left']+1, bounds
        assert bounds['dateRight'] <= bounds['right']-1, bounds
        assert abs(bounds['scrollLeft']) <= 1, bounds
        return bounds

    assert date_is_inside_viewport()['vertical'] is True
    initial_calls = evaluate('qa.calls.length')
    change(evaluate, 'transactionFilterQuery', '88059ESH8', 'input')
    assert ids(evaluate) == ['bond']
    assert date_is_inside_viewport()['vertical'] is False
    # A longer saved disclosure restores vertical scrolling. Collapsing it,
    # sorting and rerendering must not reserve an obsolete RTL scrollbar gutter.
    evaluate("state.localTransactions.find(tx=>tx.id==='bond').comments+='\\n'+Array(45).fill('Synthetic long saved comment').join('\\n');renderLocalTransactions();")
    date_is_inside_viewport()
    evaluate("document.querySelector('[data-transaction-id=bond] summary').click();$('securitiesList').scrollLeft=0;")
    assert date_is_inside_viewport()['vertical'] is True
    change(evaluate, 'transactionFilterTo', '31/02/2026')
    assert ids(evaluate) == ['bond']
    sort(evaluate, 'date', 'asc')
    date_is_inside_viewport()
    evaluate("document.querySelector('[data-transaction-id=bond] summary').click();$('securitiesList').scrollLeft=0;")
    assert date_is_inside_viewport()['vertical'] is False
    evaluate('renderLocalTransactions();renderLocalTransactions();')
    date_is_inside_viewport()
    evaluate("$('resetTransactionFilters').click()")
    assert len(ids(evaluate)) == 11
    assert date_is_inside_viewport()['vertical'] is True
    assert evaluate('qa.calls.length') == initial_calls
    assert evaluate('qa.writes') == []
    assert evaluate('qa.errors') == []
