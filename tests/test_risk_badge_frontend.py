"""Numeric-only risk badges retain their meaning and accessible interactions."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run_node(script):
    result = subprocess.run(['node'], input=script, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_all_risk_bands_show_only_the_number_and_keep_localized_accessible_details():
    source = (ROOT / 'web/app.js').read_text()
    functions = []
    for name in ('locale', 'esc', 'fmt', 'optionLabel', 'riskBand', 'riskTooltip', 'riskBadge'):
        start = source.index(f'function {name}(')
        end = start + re.search(r'^}', source[start:], re.M).end()
        functions.append(source[start:end])
    run_node("const assert=require('node:assert/strict');const window={};const OPTION_LABELS={};const state={language:'en'};\n"
             + (ROOT / 'web/i18n.js').read_text() + '\n' + '\n'.join(functions) + r'''
const cases=[[0,'low','Low'],[20,'low','Low'],[21,'moderate','Moderate'],[40,'moderate','Moderate'],[41,'elevated','Elevated'],[60,'elevated','Elevated'],[61,'high','High'],[80,'high','High'],[81,'extreme','Extreme'],[100,'extreme','Extreme']];
for(const language of ['en','he']){
 state.language=language;
 for(const [score,key,label] of cases){
  const risk={score,label:'Account "A" <test>',drivers:[],components:{}};
  const original=JSON.stringify(risk),html=riskBadge(risk),tooltip=riskTooltip(risk);
  assert.equal(html.replace(/<[^>]*>/g,'').trim(),String(score));
  assert.ok(html.startsWith('<button')&&html.includes(`risk-${key}`));
  assert.ok(html.includes(`aria-describedby="riskBadgeExplanation"`));
  assert.ok(html.includes(esc(`${optionLabel('Risk')}: ${score} · ${optionLabel(label)}`)));
  assert.ok(!html.includes('risk-symbol')&&!html.includes('<script>'));
  assert.ok(!tooltip.split('\n')[0].includes('/100'));
  assert.ok(tooltip.includes(optionLabel('This is a model-based risk estimate, not a probability or forecast of loss.')));
  assert.equal(JSON.stringify(risk),original);
 }
}
for(const score of [null,undefined,NaN,Infinity,'',true,-1,101])assert.equal(riskBadge({score}),'');
assert.equal(riskBadge(null),'');
''')


def test_shared_explanation_hover_focus_pin_escape_outside_and_stale_source():
    run_node(r'''
const assert=require('node:assert/strict');
const handlers={};let mutation,pendingHide;
global.setTimeout=fn=>{pendingHide=fn;return 1};global.clearTimeout=()=>{pendingHide=null};
const finishPointerExit=()=>{const next=pendingHide;pendingHide=null;if(next)next()};
const popup={hidden:true,textContent:'',style:{},contains:n=>n===popup,getBoundingClientRect:()=>({width:300,height:Math.min(400,parseFloat(popup.style.maxHeight)||400)})};
let scrollOffset=0;
Object.defineProperty(popup,'scrollTop',{get:()=>popup.hidden?0:scrollOffset,set:value=>{if(!popup.hidden)scrollOffset=value}});
const outside={};
const control={dataset:{riskExplanation:'Moderate risk · 29\nModel explanation'},isConnected:true,
 contains:n=>n===control,closest:()=>control,getBoundingClientRect:()=>({left:340,top:640,bottom:680})};
global.document={body:{},activeElement:null,getElementById:()=>popup,addEventListener:(name,fn)=>{(handlers[name]??=[]).push(fn)}};
global.window={addEventListener:(name,fn)=>{(handlers[name]??=[]).push(fn)}};
global.innerWidth=390;global.innerHeight=720;
global.MutationObserver=class{constructor(fn){mutation=fn}observe(){}};
const fire=(name,target,extra={})=>{const e={target,relatedTarget:null,...extra};for(const fn of handlers[name]||[])fn(e);};
''' + (ROOT / 'web/risk-badge-ui.js').read_text() + r'''
fire('pointerover',control,{pointerType:'mouse'});
assert.equal(popup.hidden,false);assert.equal(popup.textContent,control.dataset.riskExplanation);
assert.ok(parseFloat(popup.style.left)>=12&&parseFloat(popup.style.left)+300<=378);
assert.ok(parseFloat(popup.style.top)>=12&&parseFloat(popup.style.top)+400<=708);
fire('pointerout',control,{relatedTarget:popup});assert.equal(popup.hidden,false);
fire('pointerout',popup,{relatedTarget:outside});finishPointerExit();assert.equal(popup.hidden,true);
fire('pointerover',control,{pointerType:'mouse'});
fire('pointerout',control,{relatedTarget:outside});fire('pointerover',popup,{pointerType:'mouse'});
finishPointerExit();assert.equal(popup.hidden,false,'pointer can cross the small gap to read or scroll details');
fire('pointerout',popup,{relatedTarget:outside});finishPointerExit();assert.equal(popup.hidden,true);
document.activeElement=control;fire('focusin',control);assert.equal(popup.hidden,false);
popup.scrollTop=90;fire('focusin',control);assert.equal(popup.scrollTop,90,'same explanation keeps reading position');
popup.scrollHeight=1000;popup.clientHeight=350;
fire('keydown',control,{key:'PageDown',preventDefault(){},stopImmediatePropagation(){}});assert.equal(popup.scrollTop,400);
fire('keydown',control,{key:'End',preventDefault(){},stopImmediatePropagation(){}});assert.equal(popup.scrollTop,650);
fire('keydown',control,{key:'Home',preventDefault(){},stopImmediatePropagation(){}});assert.equal(popup.scrollTop,0);
control.dataset.riskExplanation+='\nUpdated evidence';fire('focusin',control);assert.equal(popup.scrollTop,0,'changed evidence starts at the category header');
document.activeElement=outside;fire('focusout',control,{relatedTarget:outside});assert.equal(popup.hidden,true);
fire('focusin',control);assert.equal(popup.scrollTop,0,'reopening starts at the top');
fire('focusout',control,{relatedTarget:outside});
fire('pointerover',control,{pointerType:'touch'});assert.equal(popup.hidden,true);
fire('click',control);fire('pointerout',control,{relatedTarget:outside});assert.equal(popup.hidden,false);
fire('click',control);assert.equal(popup.hidden,true);
fire('click',control);fire('click',outside);assert.equal(popup.hidden,true);
fire('click',control);
let prevented=false,stopped=false;
fire('keydown',control,{key:'Escape',preventDefault(){prevented=true},stopImmediatePropagation(){stopped=true}});
assert.ok(popup.hidden&&prevented&&stopped);
fire('click',control);control.isConnected=false;mutation();assert.equal(popup.hidden,true);
control.isConnected=true;control.dataset.riskExplanation='Updated category and evidence';
document.activeElement=control;fire('focusin',control);assert.equal(popup.textContent,control.dataset.riskExplanation);
control.getBoundingClientRect=()=>({left:50,top:300,bottom:344});fire('resize',outside);
const top=parseFloat(popup.style.top),height=popup.getBoundingClientRect().height;
assert.ok(top>=344||top+height<=300,'the explanation must not cover its tap-to-close score');
assert.ok(top>=12&&top+height<=708);
control.getBoundingClientRect=()=>({left:30,top:-90,bottom:-50});fire('scroll',outside);assert.equal(popup.hidden,true);
''')
