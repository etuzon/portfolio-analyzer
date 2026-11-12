"""Independent actual browser checks for holdings order and keyboard controls."""
import base64

import pytest

from test_native_account_history_qa import chromium
from test_risk_scenarios_qa import browser_document,browser_wait


@pytest.mark.parametrize(('language','width'), [(language,width) for language in ('en','he') for width in (1440,1024,800,761,390)])
def test_sort_controls_visible_keyboard_numeric_fx_missing_and_background(tmp_path,chromium,language,width):
    command,evaluate=chromium
    command('Emulation.setDeviceMetricsOverride',dict(width=width,height=1080,deviceScaleFactor=1,mobile=False))
    command('Page.navigate',{'url':browser_document(tmp_path,language).as_uri()})
    browser_wait(evaluate,'window.qa?.ready===true')
    evaluate(r'''(()=>{
      const row=(symbol,value,currency='USD')=>{const item=structuredClone(qa.context.items[0]);
        Object.assign(item.holding,{symbol,market_value:value,currency,unrealized_profit:value,account:'A'});
        item.moving_averages={};item.support_resistance={};return item;};
      qa.rows=[row('Ten',10),row('Two',2),row('FX',3,'EUR'),row('Missing',null),row('NoFX',900,'JPY')];
      state.baseCurrency='USD';state.fxRates={'EUR/USD':2};state.items=qa.rows;renderRows(qa.rows);
      document.querySelector('.holdings-table-wrap').scrollIntoView();
    })()''')
    assert evaluate('qa.errors')==[]
    # Native controls stay accessible when mobile holdings rows become cards.
    if width<=760:
        assert evaluate("$('holdingsMobileSort').checkVisibility()"), 'Mobile sorting is hidden'
        assert evaluate("!document.querySelector('[data-holdings-sort=value]').checkVisibility()")
        evaluate("$('holdingsMobileSort').focus()")
        for _ in range(4):
            command('Input.dispatchKeyEvent',{'type':'keyDown','key':'ArrowDown','code':'ArrowDown','windowsVirtualKeyCode':40})
            command('Input.dispatchKeyEvent',{'type':'keyUp','key':'ArrowDown','code':'ArrowDown','windowsVirtualKeyCode':40})
        assert evaluate("$('holdingsMobileSort').value")=='value'
        evaluate("$('holdingsMobileSortDirection').focus()")
        focused="document.activeElement.id==='holdingsMobileSortDirection'"
    else:
        assert evaluate("document.querySelector('[data-holdings-sort=value]').checkVisibility()")
        assert evaluate("document.querySelector('[data-holdings-sort=value]').getBoundingClientRect().height>=24")
        clipped=evaluate("[...document.querySelectorAll('[data-holdings-sort]')].flatMap(n=>{const b=n.getBoundingClientRect(),h=n.closest('th').getBoundingClientRect();return b.left>=h.left-1&&b.right<=h.right+1?[]:[{key:n.dataset.holdingsSort,left:b.left,right:b.right,columnLeft:h.left,columnRight:h.right}];})")
        if clipped:
            image=command('Page.captureScreenshot',{'format':'png'})
            (tmp_path/f'clipped-{language}-{width}.png').write_bytes(base64.b64decode(image['data']))
        assert not clipped, clipped
        evaluate("document.querySelector('[data-holdings-sort=value]').focus()")
        command('Input.dispatchKeyEvent',{'type':'keyDown','key':'Enter','code':'Enter','windowsVirtualKeyCode':13,'text':'\r'})
        command('Input.dispatchKeyEvent',{'type':'keyUp','key':'Enter','code':'Enter','windowsVirtualKeyCode':13})
        focused="document.activeElement.matches('[data-holdings-sort=value]')"
    order="[...$('rows').querySelectorAll('[data-security-detail-symbol]')].map(n=>n.dataset.securityDetailSymbol)"
    assert evaluate(order)==['Ten','FX','Two','Missing','NoFX']
    assert evaluate("document.querySelector('[data-holdings-sort=value]').closest('th').getAttribute('aria-sort')")=='descending'
    assert evaluate(focused)
    command('Input.dispatchKeyEvent',{'type':'keyDown','key':' ','code':'Space','windowsVirtualKeyCode':32,'text':' '})
    command('Input.dispatchKeyEvent',{'type':'keyUp','key':' ','code':'Space','windowsVirtualKeyCode':32})
    assert evaluate(order)==['Two','FX','Ten','Missing','NoFX']
    # Filtering and new source order preserve the active key and direction.
    evaluate('renderRows([...qa.rows].reverse())')
    assert evaluate(order)==['Two','FX','Ten','NoFX','Missing']
    evaluate('renderRows([qa.rows[0],qa.rows[1]])')
    assert evaluate(order)==['Two','Ten']
    label=evaluate("document.querySelector('[data-holdings-sort=value]').getAttribute('aria-label')")
    if language=='he':assert 'Sort by' not in label and 'מיון' in label
    else:assert 'Sort by' in label and 'dashboard currency' in label
    if width<=760:
        visible=evaluate("document.querySelector('.holdings-mobile-sort').innerText")
        if language=='he':assert 'Original order' not in visible and 'Sort by' not in visible
        assert evaluate("$('holdingsMobileSort').getBoundingClientRect().width>=150")
    assert evaluate('qa.calls.length')==0
    assert evaluate('qa.errors')==[]
    if width>760:
        assert evaluate("[...document.querySelectorAll('.holdings-sort-group')].every(group=>{const rows=[...group.children].map(n=>n.getBoundingClientRect().top);return Math.max(...rows)-Math.min(...rows)<=1;})"), 'Grouped desktop controls unexpectedly stack'
        # Keyboard navigation can reveal and activate the far technical column.
        evaluate("document.querySelector('[data-holdings-sort=ma]').focus()")
        command('Input.dispatchKeyEvent',{'type':'keyDown','key':'Enter','code':'Enter','windowsVirtualKeyCode':13,'text':'\r'})
        command('Input.dispatchKeyEvent',{'type':'keyUp','key':'Enter','code':'Enter','windowsVirtualKeyCode':13})
        assert evaluate("document.querySelector('[data-holdings-sort=ma]').getAttribute('aria-pressed')")=='true'
    image=command('Page.captureScreenshot',{'format':'png'})
    (tmp_path/f'holdings-sort-{language}-{width}.png').write_bytes(base64.b64decode(image['data']))
