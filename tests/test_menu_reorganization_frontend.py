"""Navigation destinations, merged workspaces and accessible tab transitions."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "web/app.js").read_text()


def functions(*names):
    result = []
    for name in names:
        start = re.search(rf"^function {name}\(", SOURCE, re.M).start()
        end = re.search(r"^}", SOURCE[start:], re.M).end()
        result.append(SOURCE[start:start + end])
    return "\n".join(result)


def run_js(code):
    result = subprocess.run(["node"], input=code, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_seven_task_groups_keep_all_destinations_and_role_permissions():
    run_js("const window={};\n" + (ROOT / "web/i18n.js").read_text() + r'''
const assert=require('node:assert/strict');
const labels={positions:'Positions',prices:'Prices',research:'Research',marketScreener:'Market Screener',signalRules:'Portfolio Signals',accounts:'Accounts',brokers:'Brokers',familyMembers:'Family Members',accountOwnership:'Account Ownership',pensionsFunds:'Pensions & Funds',retirementProjections:'Retirement Projections',employeeOptions:'Employee Stock Options',settings:'Settings',marketBanner:'Market Banner',users:'Users',help:'Help',about:'About'};
let language='en',admin=false;
const t=value=>window.PortfolioI18n.translate(labels[value]||value,language);
const esc=value=>String(value).replaceAll('&','&amp;');
const canAdmin=()=>admin;const $=()=>null;
const nav={innerHTML:'',querySelector:()=>null};
const document={querySelector:()=>nav};
const navMenuSummary=(_icon,label)=>`<summary>${esc(label)}</summary>`;
''' + functions("ensureHierarchicalNav") + r'''
const groups=['Portfolio','Research','Calculations','Accounts & People','Retirement & Benefits','Settings','Help'];
const destinations=[['positionsModal','securitiesModal','tradingJournalModal','eventsModal','pricesModal','reportsModal'],['marketModal','researchModal','researchModal','macroScenarioModal'],['tradeSimulatorModal','varModal','correlationModal','benchmarkModal','optimizationModal','xrayModal'],['accountsModal','brokersModal','familyModal','familyModal'],['fundsModal','fundsModal','securitiesModal'],['settingsModal','bannerModal'],['helpModal','aboutModal']];
for(language of ['en','he','en'])for(admin of [false,true]){
 ensureHierarchicalNav();
 const menus=[...nav.innerHTML.matchAll(/<details class="nav-menu"[^>]*>\s*<summary>(.*?)<\/summary>([\s\S]*?)<\/details>/g)];
 assert.equal(menus.length,7);
 menus.forEach((menu,index)=>{
  assert.equal(menu[1],esc(t(groups[index])));
  const actual=[...menu[2].matchAll(/data-modal="([^"]+)"/g)].map(row=>row[1]);
  assert.deepEqual(actual,index===5&&admin?[...destinations[index],'usersModal']:destinations[index]);
 });
 assert.equal((nav.innerHTML.match(/data-modal="varModal"/g)||[]).length,1);
 assert.ok(nav.innerHTML.includes('data-research-section="finance"'));
 assert.ok(nav.innerHTML.includes('data-research-section="signals"'));
 assert.ok(menus[4][2].includes('data-securities-workflow="employee-options"'));
 assert.ok(!menus[0][2].includes('employee-options'));
 if(language==='he')assert.ok(!/Portfolio|Research|Calculations|Transactions|Company Analysis|Settings|User Guide/.test(nav.innerHTML));
}
''')


def test_company_analysis_signals_and_merged_dividend_tabs_preserve_controls_and_retry():
    run_js(r'''
const assert=require('node:assert/strict');const state={language:'en'};const t=value=>value;
const node=dataset=>({dataset,hidden:false,attrs:{},classList:{toggle(){}},setAttribute(key,value){this.attrs[key]=value;}});
const researchTabs=['finance','outlook','signals'].map(value=>node({researchTab:value}));
const researchPanels=['finance','outlook','signals'].map(value=>node({researchPanel:value}));
const dividendTabs=['calendar','events'].map(value=>node({dividendsTab:value}));
const dividendPanels=['calendar','events'].map(value=>node({dividendsPanel:value}));
const nodes={researchTitle:{},researchTabs:{},researchDescription:{},eventsStatus:{},dividendCalendarAccount:{value:'one'},dividendCalendarYear:{value:'2024'}};
const $=id=>nodes[id];
const document={querySelectorAll:selector=>({'[data-research-tab]':researchTabs,'[data-research-panel]':researchPanels,'[data-dividends-tab]':dividendTabs,'[data-dividends-panel]':dividendPanels}[selector])};
let calendarLoads=0,eventLoads=0,fail=true;
const loadDividendCalendar=()=>{calendarLoads++;};
const loadEvents=()=>{eventLoads++;return fail?Promise.reject(new Error('private response')):Promise.resolve();};
''' + functions("setResearchSection", "setDividendsSection") + r'''
(async()=>{
 setResearchSection('outlook');assert.equal(nodes.researchTitle.textContent,'Company Analysis');assert.equal(researchPanels[1].hidden,false);assert.equal(researchTabs[2].hidden,true);
 setResearchSection('signals');assert.equal(nodes.researchTitle.textContent,'Portfolio Signals');assert.equal(nodes.researchTabs.hidden,true);assert.equal(researchPanels[2].hidden,false);assert.equal(researchTabs[2].tabIndex,-1);
 setResearchSection('finance');assert.equal(nodes.researchTabs.hidden,false);assert.equal(researchPanels[0].hidden,false);assert.equal(researchPanels[2].hidden,true);
 setDividendsSection();assert.equal(calendarLoads,1);assert.equal(eventLoads,0);assert.equal(dividendPanels[0].hidden,false);assert.equal(dividendPanels[1].hidden,true);
 setDividendsSection('events');await new Promise(resolve=>setImmediate(resolve));
 assert.equal(eventLoads,1);assert.equal(dividendTabs[1].attrs['aria-selected'],'true');assert.equal(dividendTabs[0].tabIndex,-1);
 assert.ok(nodes.eventsStatus.textContent.includes('Select Events again'));assert.ok(!nodes.eventsStatus.textContent.includes('private'));
 fail=false;setDividendsSection('events');assert.equal(eventLoads,2);
 setDividendsSection('calendar',{load:false});assert.equal(calendarLoads,1);
 assert.equal(nodes.dividendCalendarAccount.value,'one');assert.equal(nodes.dividendCalendarYear.value,'2024');
})();
''')


def test_tab_keyboard_skips_hidden_tabs_and_follows_interface_direction():
    run_js(r'''
const assert=require('node:assert/strict');const state={language:'en'};
let focused=-1,clicked=-1;
const tabs=[0,1,2].map(index=>({hidden:index===2,disabled:false,focus(){focused=index;},click(){clicked=index;},closest(){return scope;}}));
const scope={querySelectorAll:()=>tabs};
const event=(index,key)=>({key,target:{closest:()=>tabs[index]},preventDefault(){this.prevented=true;}});
''' + functions("moveWorkspaceTab") + r'''
for(const [language,index,key,expected] of [['en',1,'ArrowRight',0],['en',0,'End',1],['en',1,'Home',0],['he',0,'ArrowLeft',1],['he',0,'ArrowRight',1]]){
 state.language=language;const e=event(index,key);assert.equal(moveWorkspaceTab(e,'[data-research-tab]'),true);assert.equal(focused,expected);assert.equal(clicked,expected);assert.equal(e.prevented,true);
}
assert.equal(moveWorkspaceTab({key:'Enter',target:{closest:()=>null}},'[data-dividends-tab]'),false);
''')


def test_old_calendar_links_open_merged_dialog_and_alarms_target_events():
    run_js(r'''
const assert=require('node:assert/strict');class HTMLElement{}
const trigger=new HTMLElement();const document={activeElement:trigger};
const modal={id:'eventsModal',hidden:true,parentElement:{append(){}}};
const $=id=>id==='eventsModal'?modal:null;const modalReturnFocus=new Map();
const mountModalHomeLink=()=>{};const focusModalDestination=()=>{};const sections=[];
const setDividendsSection=section=>sections.push(section);
''' + functions("openModal") + r'''
openModal('dividendCalendarModal',trigger);assert.equal(modal.hidden,false);assert.equal(sections.at(-1),'calendar');assert.equal(modalReturnFocus.get('eventsModal'),trigger);
openModal('eventsModal',trigger,{dividendsSection:'events'});assert.equal(sections.at(-1),'events');
openModal('eventsModal',trigger);assert.equal(sections.at(-1),'calendar');
''' + r'''
const state={};let focused=0;const focusEventRow=()=>{focused++;};const setTimeout=callback=>callback();
''' + functions("openDividendAlarm") + r'''
openDividendAlarm('event-one');assert.equal(state.focusedEventId,'event-one');assert.equal(sections.at(-1),'events');assert.equal(focused,1);
''')
