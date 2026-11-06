"""The net-income column displays the supplied change with honest sign/units."""
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def test_net_income_percentage_preserves_periods_and_unavailable_states():
    source=(ROOT/'web/app.js').read_text()
    functions=[]
    for name in ('trendCell','analyticsStateCell','seriesDate','changeClass','changeText'):
        start=source.index(f'function {name}(')
        end=re.search(r'^}',source[start:],re.M).end()
        functions.append(source[start:start+end])
    script=r'''
const assert=require('node:assert/strict');
const t=value=>value;
const esc=value=>String(value).replaceAll('<','&lt;').replaceAll('>','&gt;');
const pct=value=>`${Math.round(value*100)/100}%`;
const formatDate=value=>value.split('-').reverse().join('/');
const formatMetricValue=value=>String(value);
const compactMoney=(value,currency)=>`${currency} ${value}`;
const series=[{date:'2022-12-31',value:100},{date:'2025-12-31',value:110}];
'''+'\n'.join(functions)+r'''
for(const [previous,current,change,text,css] of [[100,110,10,'+10%','up'],[100,90,-10,'-10%','down'],[100,100,0,'0%','neutral'],[-100,-50,50,'+50%','up'],[-100,50,150,'+150%','up'],[-100,-150,-50,'-50%','down'],[100,-100,-200,'-200%','down'],[100,100.1,0.1,'+0.1%','up'],[100,100.001,0.001,'+&lt;0.01%','up'],[100,99.999,-0.001,'−&lt;0.01%','down']]){
 const html=trendCell({state:'ok',direction:'flat',current,previous,percent_change:change,series},'Net income',{displayPercent:true});
 assert.ok(html.includes(`metric-pill ${css}`));assert.ok(html.includes(text),html);
 assert.ok(html.includes('<bdi dir="ltr">'));
 assert.ok(html.includes('31/12/2022'));assert.ok(html.includes('31/12/2025'));
 assert.ok(!html.includes('YoY'));
}
for(const percent_change of [null,undefined,NaN,Infinity,-Infinity,'10',false]){
 const html=trendCell({state:'ok',current:10,previous:0,percent_change,series},'Net income',{displayPercent:true});
 assert.ok(html.includes('metric-pill warn'));assert.ok(html.includes('Not available'));
 assert.ok(!html.includes('>0%<'));assert.ok(!html.includes('metric-pill neutral'));
}
for(const state of ['pending','error','missing']){
 const html=trendCell({state,series},'Net income',{displayPercent:true});
 assert.ok(!html.includes('>0%<'));
 assert.ok(html.includes(state==='pending'?'Loading':state==='error'?'could not be updated':'Missing'));
}
const dividend=trendCell({state:'ok',current:2,previous:1,percent_change:100,series},'Annual dividend');
assert.ok(dividend.includes('>Up</span>'));
'''
    result=subprocess.run(['node'],input=script,text=True,capture_output=True,cwd=ROOT)
    assert result.returncode==0,result.stderr
