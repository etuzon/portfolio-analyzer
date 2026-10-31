"""Rule filtering narrows signals without rewriting the builder or source data."""
from test_signal_dismissal_frontend import functions, run_js


def run_filter(body):
    run_js(functions("renderAlerts", "alertRunIsActive", "alertRunStatusText", "alertRunProgressText") + r'''
const assert=require('node:assert/strict');
const state={language:'he',alertConditions:[{metric:'draft',value:7}],alertRuleFilter:''};
const nodes={};
const $=id=>nodes[id]||=( {innerHTML:'',textContent:'',value:''} );
const esc=value=>String(value??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const fmt=value=>String(value);
const formatDateTime=()=> '31/10/2026';
let builderRenders=0,pollSchedules=0;
const renderAlertConditions=()=>{builderRenders++};
const resetAlertForm=()=>{builderRenders++};
const scheduleAlertRefresh=()=>{pollSchedules++};
const alertConditionText=()=> 'condition';
const initial={rules:[{id:'a',name:'Income',enabled:true},{id:'b',name:'Income',enabled:true},{id:'empty',name:'Empty',enabled:false}],runs:[],active_signals:[
 {rule_id:'a',rule_name:'Income',symbol:'NEWT',signal:'buy'},
 {rule_id:'a',rule_name:'Income',symbol:'NREF',signal:'buy'},
 {rule_id:'b',rule_name:'Income',symbol:'NEWT',signal:'buy'}]};
''' + body)


def test_filter_uses_rule_ids_disambiguates_names_and_keeps_builder_and_totals_intact():
    run_filter(r'''
renderAlerts(initial);
assert.ok(nodes.alertRuleFilter.innerHTML.includes('Income (1)')&&nodes.alertRuleFilter.innerHTML.includes('Income (2)'));
const before=JSON.stringify(initial),conditions=JSON.stringify(state.alertConditions);
nodes.alertConditions={innerHTML:'unsaved user values'};nodes.alertName={value:'Unsaved rule name'};
const savedRules=nodes.alertsList.innerHTML;
const renders=builderRenders,schedules=pollSchedules;
state.alertRuleFilter='rule:a';
renderAlerts(initial,{signalsOnly:true});
assert.equal((nodes.alertsSignals.innerHTML.match(/data-signal-rule=/g)||[]).length,2);
assert.ok(!nodes.alertsSignals.innerHTML.includes('data-signal-rule="rule:b"'));
assert.equal(nodes.alertActiveSummary.textContent,'3');
assert.equal(nodes.alertSignalFilterCount.textContent,'איתותים מוצגים: 2 מתוך 3');
assert.equal(nodes.alertRuleFilter.value,'rule:a');
assert.equal(nodes.alertConditions.innerHTML,'unsaved user values');
assert.equal(nodes.alertName.value,'Unsaved rule name');
assert.equal(nodes.alertsList.innerHTML,savedRules);
assert.equal(builderRenders,renders);assert.equal(pollSchedules,schedules);
assert.equal(JSON.stringify(state.alertConditions),conditions);
assert.equal(JSON.stringify(initial),before);
state.alertRuleFilter='rule:b';renderAlerts(initial,{signalsOnly:true});
assert.equal((nodes.alertsSignals.innerHTML.match(/data-signal-rule=/g)||[]).length,1);
assert.ok(nodes.alertsSignals.innerHTML.includes('Income (2)'));
''')


def test_selection_survives_updates_and_language_changes_with_clear_empty_and_deleted_rule_states():
    run_filter(r'''
state.alertRuleFilter='rule:empty';renderAlerts(initial);
assert.equal(nodes.alertRuleFilter.value,'rule:empty');
assert.ok(nodes.alertsSignals.innerHTML.includes('אין איתותים התואמים לכלל שנבחר'));
state.language='en';renderAlerts(initial,{signalsOnly:true});
assert.equal(nodes.alertRuleFilter.value,'rule:empty');
assert.ok(nodes.alertsSignals.innerHTML.includes('No signals match the selected rule.'));
assert.ok(!/[א-ת]/.test(nodes.alertRuleFilter.innerHTML+nodes.alertSignalFilterCount.textContent+nodes.alertsSignals.innerHTML));
renderAlerts({...initial,rules:initial.rules.filter(rule=>rule.id!=='empty')});
assert.equal(state.alertRuleFilter,'');assert.equal(nodes.alertRuleFilter.value,'');
assert.equal((nodes.alertsSignals.innerHTML.match(/data-signal-rule=/g)||[]).length,3);
state.alertRuleFilter='rule:a';
renderAlerts({...initial,active_signals:[...initial.active_signals,{rule_id:'a',rule_name:'Income',symbol:'OBDC',signal:'buy'}]});
assert.equal(nodes.alertRuleFilter.value,'rule:a');
assert.equal(nodes.alertSignalFilterCount.textContent,'Signals shown: 3 of 4');
''')


def test_orphan_legacy_rules_escaping_and_local_dismissals_stay_consistent_with_filter():
    run_filter(r'''
const payload={rules:[],runs:[],active_signals:[
 {rule_id:'gone',rule_name:'<Retired & rule>',symbol:'NEWT',signal:'buy'},
 {rule_name:'Legacy',symbol:'NREF',signal:'watch'},
 {symbol:'OBDC',signal:'sell'}]};
renderAlerts(payload);
assert.ok(nodes.alertRuleFilter.innerHTML.includes('&lt;Retired &amp; rule&gt;'));
state.alertRuleFilter='rule:gone';renderAlerts(payload,{signalsOnly:true});
assert.ok(nodes.alertsSignals.innerHTML.includes('NEWT'));
state.alertRuleFilter='name:Legacy';renderAlerts(payload,{signalsOnly:true});
assert.ok(nodes.alertsSignals.innerHTML.includes('NREF')&&!nodes.alertsSignals.innerHTML.includes('NEWT'));
state.alertRuleFilter='unassigned';renderAlerts(payload,{signalsOnly:true});
assert.ok(nodes.alertsSignals.innerHTML.includes('OBDC'));
state.alertRuleFilter='rule:gone';
state.alertClientDismissals=[{symbol:'NEWT',signal:'buy',expires_at:'2999-01-01T00:00:00Z'}];
renderAlerts(payload,{signalsOnly:true});
assert.equal(state.alertRuleFilter,'');
assert.equal(nodes.alertActiveSummary.textContent,'2');
assert.ok(!nodes.alertsSignals.innerHTML.includes('NEWT'));
''')
