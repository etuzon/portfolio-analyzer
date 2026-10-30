import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'web/app.js').read_text()


def functions(*names):
    result = []
    for name in names:
        start = re.search(rf'^(?:async )?function {name}\(', SOURCE, re.M).start()
        end = re.search(r'^}', SOURCE[start:], re.M).end()
        result.append(SOURCE[start:start + end])
    return '\n'.join(result)


def run(script):
    completed = subprocess.run(['node'], input=script, check=True, capture_output=True, text=True)
    return json.loads(completed.stdout) if completed.stdout else None


def test_trade_history_filters_keep_closed_positions_and_reopened_periods():
    run(functions('filteredTradeHistoryItems', 'positionMonetarySort') + """
const assert=require('node:assert/strict');
const nodes={tradeHistoryPositionStatus:{value:'all'},tradeHistorySearch:{value:''}};
const valueOf=id=>nodes[id]?.value || '';
const positionAccountMatchesFilters=()=>true;
const locale=()=> 'en';
const formatDate=value=>value.split('-').reverse().join('/');
const state={tradeHistory:{items:[
 {id:'old',symbol:'ABC',name:'Alpha',account_label:'Account A',status:'closed',opened_date:'2025-01-01',closed_date:'2025-12-30'},
 {id:'new',symbol:'ABC',name:'Alpha',account_label:'Account A',status:'open',opened_date:'2026-01-01'},
 {id:'other',symbol:'DEF',name:'Delta',account_label:'Account B',status:'closed',opened_date:'2026-02-01',closed_date:'2026-03-01'}]}};
assert.equal(filteredTradeHistoryItems().length,3);
nodes.tradeHistoryPositionStatus.value='closed';
assert.deepEqual(filteredTradeHistoryItems().map(row=>row.id),['other','old']);
nodes.tradeHistorySearch.value='alpha';
assert.deepEqual(filteredTradeHistoryItems().map(row=>row.id),['old']);
nodes.tradeHistorySearch.value='30/12/2025';
assert.deepEqual(filteredTradeHistoryItems().map(row=>row.id),['old']);
""")


def test_csv_preserves_numeric_losses_and_neutralizes_formula_text():
    run(functions('tradeHistoryCsvCell') + r"""
const assert=require('node:assert/strict');
assert.equal(tradeHistoryCsvCell(-12.34),'"-12.34"');
assert.equal(tradeHistoryCsvCell(null),'""');
assert.equal(tradeHistoryCsvCell('=HYPERLINK("bad")'),'"\'=HYPERLINK(""bad"")"');
assert.equal(tradeHistoryCsvCell(' +SUM(A1)'),'"\' +SUM(A1)"');
assert.equal(tradeHistoryCsvCell('Account, A'),'"Account, A"');
""")


def test_operational_history_states_and_actions_are_localized():
    labels = [
        'Loading recorded trade history…', 'Could not load trade history. Retry to load this section.',
        'Open position', 'Closed position', 'Holding periods', 'Saved local prices',
        'Realized P/L', 'Unrealized P/L', 'Total P/L', 'P/L per day', 'P/L per year',
        'Purchase date unavailable — imported position snapshot',
        'Daily and yearly P/L are unavailable for a same-day position',
        'Some history data is incomplete', 'Retry', 'Details', 'Limited data',
        'Buy', 'Sell', 'Add', 'Remove', 'Short', 'Dividend', 'Interest', 'Fee',
        'Positions', 'Position filters', 'Account name', 'Sort by', 'Sort direction',
        'Ascending', 'Descending', 'Reset filters', 'Opened date', 'Closed date', 'All securities',
    ]
    result = run('const window={};\n' + (ROOT / 'web/i18n.js').read_text() + '\nconst labels=' + json.dumps(labels) + ";process.stdout.write(JSON.stringify(labels.map(label=>window.PortfolioI18n.translate(label,'he'))));")
    assert all(re.search(r'[א-ת]', label) for label in result)
    assert all(not re.search(r'[A-Za-z]', label) for label in result)


def test_late_history_response_cannot_replace_newer_data_and_failure_is_local():
    result = run(functions('loadTradeHistory') + """
const assert=require('node:assert/strict');
const state={};const requests=[];let renders=0;
const renderTradeHistory=()=>{renders++;};
const refreshPositionFilterOptions=()=>{};
const api=url=>new Promise((resolve,reject)=>requests.push({url,resolve,reject}));
(async()=>{
 const older=loadTradeHistory();
 const newer=loadTradeHistory();
 assert.deepEqual(requests.slice(0,3).map(r=>r.url),['/api/local/trade-history','/api/local/accounts','/api/local/family-members']);
 requests[3].resolve({items:[{id:'new'}]});
 requests[4].resolve({items:[{id:'new-account'}]});
 requests[5].resolve({items:[{id:'new-person'}]});await newer;
 requests[0].resolve({items:[{id:'old'}]});
 requests[1].resolve({items:[]});requests[2].resolve({items:[]});await older;
 assert.equal(state.tradeHistory.items[0].id,'new');
 assert.equal(state.positionsAccounts[0].id,'new-account');
 assert.equal(state.positionsPeople[0].id,'new-person');
 assert.equal(state.tradeHistoryLoading,false);
 const failure=loadTradeHistory();
 requests[7].reject(Error('offline'));await failure;
 assert.equal(state.tradeHistory,null);
 assert.equal(state.tradeHistoryError,true);
 assert.equal(state.tradeHistoryLoading,false);
 assert.ok(renders>=4);
 process.stdout.write(JSON.stringify('completed'));
})().catch(error=>{console.error(error);process.exitCode=1;});
""")
    assert result == 'completed'


POSITION_BASE = """
const assert=require('node:assert/strict');
const nodes={positionPerson:{value:''},positionAccountType:{value:'Investment'},positionAccount:{value:''},
 tradeHistoryPositionStatus:{value:'all'},tradeHistorySearch:{value:''},positionSort:{value:'opened_date'},positionSortDirection:{value:'desc'}};
const $=id=>nodes[id];
const valueOf=id=>nodes[id]?.value || '';
const locale=()=> 'en';
const memberLabel=member=>member.name;
const formatDate=value=>value.split('-').reverse().join('/');
const state={positionsAccounts:[
 {id:'joint',type:'Investment',persons:[{member_id:'a',name:'Alice'},{member_id:'b',name:'Bob'}]},
 {id:'solo',type:'Investment',persons:[{name:'  alice  '}]},
 {id:'pension',type:'Long-Term Savings',persons:[{member_id:'b',name:'Bob'}]}],
 positionsPeople:[{id:'a',name:'Alice'},{id:'b',name:'Bob'}],
 tradeHistory:{as_of_date:'2026-10-30',items:[
 {id:'joint-old',account_id:'joint',account_label:'Joint',symbol:'ABC',name:'Alpha',currency:'USD',status:'closed',opened_date:'2025-01-01',closed_date:'2025-12-30',total_profit:-5,duration_days:363},
 {id:'joint-new',account_id:'joint',account_label:'Joint',symbol:'ABC',name:'Alpha',currency:'USD',status:'open',opened_date:'2026-01-01',total_profit:15,duration_days:302},
 {id:'solo',account_id:'solo',account_label:'Alice account',symbol:'ZZZ',name:'Zeta',currency:'ILS',status:'closed',opened_date:'2026-02-01',closed_date:'2026-03-01',total_profit:50,duration_days:28},
 {id:'pension',account_id:'pension',account_label:'Pension',symbol:'FUND',currency:'ILS',status:'open',opened_date:null,total_profit:null,duration_days:null}]}};
"""
POSITION_FUNCTIONS = functions('positionAccountMatchesScope','positionAccountMatchesFilters','positionMonetarySort','positionStockKey','filteredTradeHistoryItems')


def test_position_filters_combine_account_type_people_name_and_status():
    run(POSITION_BASE + POSITION_FUNCTIONS + """
assert.deepEqual(filteredTradeHistoryItems().map(r=>r.id),['solo','joint-new','joint-old']);
nodes.positionPerson.value='b';
assert.deepEqual(filteredTradeHistoryItems().map(r=>r.id),['joint-new','joint-old']);
nodes.positionPerson.value='a';
assert.equal(filteredTradeHistoryItems().length,3,'shared and legacy-name ownership both match');
nodes.positionAccount.value='solo';
assert.deepEqual(filteredTradeHistoryItems().map(r=>r.id),['solo']);
nodes.positionAccount.value='';nodes.positionAccountType.value='Long-Term Savings';
assert.equal(filteredTradeHistoryItems().length,0,'filters intersect');
nodes.positionPerson.value='b';assert.equal(filteredTradeHistoryItems()[0].id,'pension');
nodes.positionAccountType.value='';nodes.positionPerson.value='';nodes.tradeHistorySearch.value='alice account';
assert.deepEqual(filteredTradeHistoryItems().map(r=>r.id),['solo']);
nodes.tradeHistorySearch.value='';nodes.tradeHistoryPositionStatus.value='closed';
assert.deepEqual(filteredTradeHistoryItems().map(r=>r.id),['solo','joint-old']);
""")


def test_position_sort_is_numeric_nulls_last_and_groups_native_currencies():
    run(POSITION_BASE + POSITION_FUNCTIONS + """
nodes.positionAccountType.value='';
nodes.positionSort.value='total_profit';
for(const dir of ['asc','desc']){
 nodes.positionSortDirection.value=dir;
 const rows=filteredTradeHistoryItems();assert.equal(rows.at(-1).id,'pension');
 assert.equal(rows[0].currency,'ILS');
 assert.deepEqual(rows.filter(r=>r.currency==='USD').map(r=>r.total_profit),dir==='asc'?[-5,15]:[15,-5]);
}
nodes.positionSort.value='duration_days';nodes.positionSortDirection.value='asc';
assert.deepEqual(filteredTradeHistoryItems().map(r=>r.id),['solo','joint-new','joint-old','pension']);
nodes.positionSortDirection.value='desc';
assert.deepEqual(filteredTradeHistoryItems().map(r=>r.id),['joint-old','joint-new','solo','pension']);
nodes.positionSort.value='closed_date';
assert.deepEqual(filteredTradeHistoryItems().slice(0,2).map(r=>r.id),['solo','joint-old']);
assert.equal(state.tradeHistory.items[0].id,'joint-old','sorting does not mutate source history');
""")


def test_positions_export_follows_filters_and_sort_before_pagination():
    run(POSITION_BASE + POSITION_FUNCTIONS + functions('tradeHistoryCsvCell','exportTradeHistoryCsv') + r"""
const t=text=>text;const currencyDisplayLabel=value=>value;const tradeHistoryIssueText=value=>value;
let output='';const Blob=class{constructor(parts){output=parts.join('');}};
const URL={createObjectURL:()=> 'fixture:csv',revokeObjectURL(){}};
const setTimeout=()=>{};
const document={createElement:()=>({click(){},remove(){}}),body:{append(){}}};
state.tradeHistory.items=Array.from({length:25},(_,i)=>({...state.tradeHistory.items[1],id:'row-'+i,total_profit:i,symbol:'STOCK'+i}));
nodes.positionSort.value='total_profit';nodes.positionSortDirection.value='asc';state.tradeHistoryPage=2;
exportTradeHistoryCsv();
const lines=output.trim().split('\r\n');assert.equal(lines.length,26,'export includes every matching page');
assert.ok(lines[1].includes('STOCK0'));assert.ok(lines.at(-1).includes('STOCK24'));
nodes.tradeHistorySearch.value='STOCK24';exportTradeHistoryCsv();assert.equal(output.trim().split('\r\n').length,2);
""")


def test_positions_navigation_and_default_are_independent_from_reports():
    html = (ROOT / 'web/index.html').read_text()
    nav = html[html.index('<nav id="appNavigation"'):html.index('</nav>')]
    portfolio_menu = nav[:nav.index('</details>')]
    assert 'data-modal="positionsModal">Positions</button>' in portfolio_menu
    run(functions('ensureHierarchicalNav') + """
const assert=require('node:assert/strict');
const nav={innerHTML:''};const document={querySelector:()=>nav};
const $=()=>null;
const NAV_MENU_ICONS={reports:''};
const canAdmin=()=>false;
const esc=value=>value;const t=value=>value;const navMenuSummary=(_icon,label)=>'<summary>'+label+'</summary>';
ensureHierarchicalNav();
const portfolio=nav.innerHTML.split('</details>')[0];
assert.ok(portfolio.includes('data-modal="positionsModal"'));
assert.ok(portfolio.indexOf('data-modal="securitiesModal">')<portfolio.indexOf('data-modal="positionsModal"'));
""")
    reports = html[html.index('<div id="reportsModal"'):html.index('<div id="positionsModal"')]
    assert 'tradeHistoryTable' not in reports
    positions = html[html.index('<div id="positionsModal"'):html.index('<div id="tradeHistoryDetailModal"')]
    assert '<option value="Investment" selected>' in positions
    for element in ['positionPerson', 'positionAccountType', 'positionAccount', 'positionStock', 'positionSort', 'positionSortDirection']:
        assert f'id="{element}"' in positions
    assert 'loadTradeHistory' not in functions('loadReports')
    reset = functions('resetPositionFilters')
    assert '$("positionAccountType").value = "Investment"' in reset
    assert '$("positionsModal").inert = true' in functions('openTradeHistoryDetails')
    assert '$("reportsModal").inert = true' not in functions('openTradeHistoryDetails')


def test_stock_filter_selects_exact_instrument_across_accounts_and_holding_periods():
    run(POSITION_BASE + POSITION_FUNCTIONS + """
nodes.positionStock={value:''};
for(const row of state.tradeHistory.items.slice(0,2)) Object.assign(row,{stock_market:'NYSE',asset_class:'EQUITY',security_id:'abc'});
const base=state.tradeHistory.items[0];
state.tradeHistory.items.push({...base,id:'other-account',account_id:'solo'},
 {...base,id:'other-market',stock_market:'TASE'}, {...base,id:'other-currency',currency:'ILS'},
 {...base,id:'other-instrument',security_id:'abc-other'});
nodes.positionStock.value=positionStockKey(base);
assert.deepEqual(new Set(filteredTradeHistoryItems().map(r=>r.id)),new Set(['joint-old','joint-new','other-account']));
nodes.positionAccount.value='joint';assert.equal(filteredTradeHistoryItems().length,2);
nodes.tradeHistoryPositionStatus.value='closed';assert.equal(filteredTradeHistoryItems()[0].id,'joint-old');
assert.equal(positionStockKey({...base,asset_class:'RSU'}),positionStockKey(base));
assert.equal(positionStockKey({...base,asset_class:'STOCK'}),positionStockKey(base));
nodes.tradeHistorySearch.value='does not exist';assert.equal(filteredTradeHistoryItems().length,0);
""")


def test_status_and_component_sorting_uses_visible_labels_and_numeric_values():
    run(POSITION_BASE + POSITION_FUNCTIONS + """
const t=label=>({'Closed position':'Z closed','Open position':'A open'}[label]||label);
nodes.positionSort.value='status';nodes.positionSortDirection.value='asc';
assert.equal(filteredTradeHistoryItems()[0].status,'open');
nodes.positionSortDirection.value='desc';assert.equal(filteredTradeHistoryItems()[0].status,'closed');
state.tradeHistory.items=Array.from({length:4},(_,i)=>({...state.tradeHistory.items[1],id:'row-'+i,
 realized_profit:[0,12,-3,null][i],unrealized_profit:[0,12,-3,null][i]}));
for(const key of ['realized_profit','unrealized_profit']){
 nodes.positionSort.value=key;
 nodes.positionSortDirection.value='asc';assert.deepEqual(filteredTradeHistoryItems().map(r=>r[key]),[-3,0,12,null]);
 nodes.positionSortDirection.value='desc';assert.deepEqual(filteredTradeHistoryItems().map(r=>r[key]),[12,0,-3,null]);
}
""")


def test_every_position_data_field_has_keyboard_sort_control_and_mobile_option():
    run(POSITION_BASE + POSITION_FUNCTIONS + functions('renderTradeHistory') + """
const t=value=>value;const esc=value=>String(value??'');const currencyDisplayLabel=value=>value;
const tradeHistoryAmount=value=>value==null?'Not available':String(value);const tradeHistoryIssueText=value=>value;
for(const id of ['tradeHistoryStatus','tradeHistoryTable','tradeHistoryUnallocated','retryTradeHistory','exportTradeHistoryCsv','positionSortNote'])nodes[id]={innerHTML:'',textContent:'',value:''};
for(const key of ['symbol','name','account_label','currency','stock_market','status','opened_date','closed_date','duration_days','total_profit','realized_profit','unrealized_profit','profit_per_day','profit_per_year']){
 nodes.positionSort.value=key;nodes.positionSortDirection.value='asc';renderTradeHistory();
 const html=nodes.tradeHistoryTable.innerHTML;
 assert.ok(html.includes('data-position-sort="'+key+'" aria-pressed="true"'),key+' has active keyboard button');
 assert.equal((html.match(/aria-sort="ascending"/g)||[]).length,1,key+' marks exactly one active column');
 const actions=html.match(/<th scope="col">Actions<\\/th>/);assert.ok(actions,'Actions has no sort control');
}
""")
    html = (ROOT / 'web/index.html').read_text()
    select = re.search(r'<select id="positionSort">(.*?)</select>', html).group(1)
    for key in ['symbol', 'name', 'account_label', 'currency', 'stock_market', 'status', 'opened_date', 'closed_date',
                'duration_days', 'total_profit', 'realized_profit', 'unrealized_profit', 'profit_per_day', 'profit_per_year']:
        assert f'value="{key}"' in select
