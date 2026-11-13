"""Real static UI with synthetic company rating histories; no AI/provider calls."""
import base64

import pytest

from test_account_cash_update_qa import browser_wait
from test_ai_enrichment_frontend import ready
from test_native_account_history_qa import chromium


@pytest.mark.parametrize('language,width', [('en', 1440), ('he', 1440), ('en', 390), ('he', 390)])
def test_current_grade_colors_and_history_tooltip_work_for_keyboard_pointer_and_touch(tmp_path, chromium, language, width):
    command, evaluate = ready(tmp_path, chromium, language, width)
    evaluate(r'''
qa.openCalls=[];openSecurityDetail=async(data,button)=>qa.openCalls.push({data,key:button.dataset.holdingsCreditKey});
qa.creditAxes={entity_name:'Example Company',scope:'issuer',scale:'global',term:'long_term',rating_type:'issuer',currency_basis:'foreign_currency'};
qa.creditOpinion=(agency,previous,rating,event_type='rating_change')=>({...qa.creditAxes,agency,status:'rated',rating,outlook:'stable',watch:'unknown',latest_change:{...qa.creditAxes,agency,origin:'public_ai',event_type,changed_fields:['rating'],previous_status:previous?'rated':null,previous_rating:previous,new_status:'rated',new_rating:rating,date_basis:previous?'agency_action':'detected',change_date:previous?'2026-11-12':null,detected_at:'2026-11-13T09:00:00Z'}});
const holding={symbol:'ACME',name:'Example Company',stock_market:'NASDAQ',platform:'NASDAQ',currency:'USD',asset_class:'EQUITY',account:'Sample account',account_id:'sample',quantity:1,market_value:10,cost_basis:9};
state.items=state.allPortfolioItems=[{holding,missing:[],price_ranges:{},moving_averages:{},support_resistance:{},api_data_route:{owner:'api'}}];
const cache=holdingsCreditRatingsSession();cache.portfolioVersion=state.portfolioLoadVersion||0;cache.requested.add('ACME|NASDAQ|USD');
const entry=holdingsCreditRatingsEntry('ACME|NASDAQ|USD');entry.state='ready';entry.context={security_key:'ACME|NASDAQ|USD',summary_only:true,ratings:[qa.creditOpinion('moodys','A1','A2'),qa.creditOpinion('sp','BBB+','AA-'),qa.creditOpinion('fitch',null,'BBB+','first_observation')]};
renderRows(state.items);applyLanguage();renderHoldingsCreditRatings();
qa.creditCell=document.querySelector('.holding-credit-ratings-cell');qa.creditMain=qa.creditCell.querySelector('[data-holdings-credit-key]');qa.creditInfo=qa.creditCell.querySelector('[data-holdings-credit-info]');
qa.creditCell.scrollIntoView({block:'center'});
''')
    assert evaluate("Array.from(qa.creditCell.querySelectorAll('[data-credit-grade-tone]')).map(n=>n.dataset.creditGradeTone)") == ['downgrade', 'upgrade', 'unchanged']
    assert evaluate("Array.from(qa.creditCell.querySelectorAll('[data-credit-grade-tone]>bdi')).map(n=>getComputedStyle(n).color)") == ['rgb(255, 104, 117)', 'rgb(110, 231, 135)', 'rgb(95, 184, 255)']
    assert not evaluate("qa.creditCell.textContent.includes('13/11/2026')||qa.creditCell.textContent.includes('First recorded')||qa.creditCell.textContent.includes('תועד לראשונה')")
    assert evaluate("qa.creditCell.querySelectorAll('[data-credit-latest-change]').length") == 0
    assert evaluate("qa.creditMain.getAttribute('aria-controls')") == 'securityDetailModal'
    assert evaluate("qa.creditInfo.getAttribute('aria-describedby')") == 'riskBadgeExplanation'
    assert not evaluate("qa.creditInfo.closest('[data-holdings-credit-key]')"), 'tooltip control is a sibling, never a nested overview button'
    description = evaluate('qa.creditInfo.dataset.explanation')
    assert 'A1 → A2' in description and 'BBB+ → AA-' in description
    assert '12/11/2026' in description and '13/11/2026' in description
    assert ('Agency action date' if language == 'en' else 'תאריך פעולת חברת הדירוג') in description
    assert ('Detected at' if language == 'en' else 'זוהה בתאריך') in description
    assert ('First recorded' if language == 'en' else 'תועד לראשונה') in description
    if language == 'he':
        assert not any(value in description for value in ['Agency rating upgraded', 'Agency rating downgraded', 'No comparable agency grade change', 'First recorded', 'Detected at'])
    command('Emulation.setFocusEmulationEnabled', {'enabled': True})
    evaluate('qa.creditMain.focus();qa.creditInfo.focus()')
    assert evaluate('document.activeElement===qa.creditInfo'), evaluate("({active:document.activeElement?.outerHTML,connected:qa.creditInfo.isConnected,rect:qa.creditInfo.getBoundingClientRect().toJSON(),errors:qa.errors})")
    assert evaluate("!$('riskBadgeExplanation').hidden"), evaluate("({rect:qa.creditInfo.getBoundingClientRect().toJSON(),panel:$('riskBadgeExplanation').outerHTML,errors:qa.errors,hasFocus:document.hasFocus()})")
    assert evaluate("$('riskBadgeExplanation').textContent") == description
    glyphs = evaluate(r"""(()=>{const node=$('riskBadgeExplanation').firstChild,text=node.textContent,result=[];
    for(const token of ['A2','AA-','BBB+']){let index=-1;while((index=text.indexOf(token,index+1))>=0){const glyphs=[];for(let i=0;i<token.length;i++){const range=document.createRange();range.setStart(node,index+i);range.setEnd(node,index+i+1);const rect=range.getBoundingClientRect();glyphs.push({x:rect.x,y:rect.y,width:rect.width});}result.push({token,glyphs});}}
    return result;})()""")
    assert {item['token'] for item in glyphs} == {'A2', 'AA-', 'BBB+'}
    for item in glyphs:
        for previous, current in zip(item['glyphs'], item['glyphs'][1:]):
            assert current['x'] > previous['x'] and abs(current['y'] - previous['y']) < 1, item
            assert abs(current['x'] - previous['x'] - previous['width']) < 2, item
    command('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'End', 'code': 'End', 'windowsVirtualKeyCode': 35})
    command('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'End', 'code': 'End', 'windowsVirtualKeyCode': 35})
    if evaluate("$('riskBadgeExplanation').scrollHeight>$('riskBadgeExplanation').clientHeight"):
        assert evaluate("$('riskBadgeExplanation').scrollTop") > 0
    geometry = evaluate("(()=>{const r=$('riskBadgeExplanation').getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,overflow:document.documentElement.scrollWidth-innerWidth,clipped:qa.creditCell.scrollWidth>qa.creditCell.clientWidth+1}})()")
    assert geometry['left'] >= 0 and geometry['right'] <= width and geometry['top'] >= 0 and geometry['bottom'] <= 1000, geometry
    assert geometry['overflow'] <= 1 and not geometry['clipped'], geometry
    (tmp_path / f'holdings-grade-tooltip-{language}-{width}.png').write_bytes(base64.b64decode(command('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': False})['data']))
    command('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Escape', 'code': 'Escape', 'windowsVirtualKeyCode': 27})
    command('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Escape', 'code': 'Escape', 'windowsVirtualKeyCode': 27})
    assert evaluate("$('riskBadgeExplanation').hidden&&document.activeElement===qa.creditInfo")
    (tmp_path / f'holdings-grade-compact-{language}-{width}.png').write_bytes(base64.b64decode(command('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': False})['data']))
    evaluate('qa.creditMain.focus()')
    command('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Tab', 'code': 'Tab', 'windowsVirtualKeyCode': 9})
    command('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Tab', 'code': 'Tab', 'windowsVirtualKeyCode': 9})
    assert evaluate('document.activeElement===qa.creditInfo')
    evaluate('qa.creditMain.focus();qa.creditCell.scrollIntoView({block:"center"})')
    tap = evaluate("(()=>{const r=qa.creditInfo.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
    for expected in [False, True]:
        command('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{**tap, 'radiusX': 2, 'radiusY': 2}]})
        command('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
        browser_wait(evaluate, "$('riskBadgeExplanation').hidden===" + str(expected).lower())
    assert evaluate('qa.openCalls.length') == 0
    evaluate(r'''qa.creditInfo.focus();qa.creditInfo.click();$('riskBadgeExplanation').scrollTop=40;qa.oldCreditScroll=$('riskBadgeExplanation').scrollTop;
    const update=holdingsCreditRatingsEntry('ACME|NASDAQ|USD');update.context.ratings[0]=qa.creditOpinion('moodys','A2','A1');renderHoldingsCreditRatings();''')
    browser_wait(evaluate, "!$('riskBadgeExplanation').hidden&&$('riskBadgeExplanation').textContent.includes('A2 → A1')")
    assert evaluate("document.activeElement===qa.creditInfo")
    assert evaluate("$('riskBadgeExplanation').scrollTop") == evaluate('qa.oldCreditScroll')
    evaluate('qa.creditMain.focus()')
    assert not evaluate("$('riskBadgeExplanation').hidden"), 'background update preserves the pinned explanation'
    assert evaluate("qa.creditCell.querySelector('[data-credit-grade-tone]').dataset.creditGradeTone") == 'upgrade'
    evaluate(r'''qa.creditInfo.focus();qa.creditBefore=scrollY;renderRows(state.items);renderHoldingsCreditRatings();
    qa.creditCell=document.querySelector('.holding-credit-ratings-cell');qa.creditMain=qa.creditCell.querySelector('[data-holdings-credit-key]');qa.creditInfo=qa.creditCell.querySelector('[data-holdings-credit-info]');''')
    assert evaluate('document.activeElement===qa.creditInfo&&Math.abs(scrollY-qa.creditBefore)<1')
    evaluate('qa.creditMain.click()')
    browser_wait(evaluate, 'qa.openCalls.length===1')
    assert evaluate('qa.errors') == []
