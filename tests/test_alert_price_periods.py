from datetime import date, timedelta
import json
from pathlib import Path
import re
import subprocess
from types import SimpleNamespace

import pytest

from app import main
from app.alerts import AlertStore, alert_rule_options
from app.metrics import price_range_metrics
from app.models import Ohlcv


def _ranges():
    today=date.today()
    return price_range_metrics([Ohlcv(today-timedelta(days=days),price,price,price,price,price,1)
                                for days,price in [(1830,40),(1600,400),(1098,150),(900,200),(366,90),(300,100),(0,80)]])


def _rows(monkeypatch,ranges):
    item={"holding":{"symbol":"PERIODQA","name":"Fixture","asset_class":"EQUITY","currency":"USD","market_value":800,"cost_basis":500,"unrealized_profit":300,"account":"Synthetic","account_id":"investment"},"price_ranges":ranges,"missing":[]}
    monkeypatch.setattr(main,"local_store",SimpleNamespace(list_accounts=lambda:[{"id":"investment","type":"Investment"}]))
    monkeypatch.setattr(main,"_portfolio_alert_source_items",lambda:([item],"cached"))
    monkeypatch.setattr(main,"config",SimpleNamespace(dashboard={"base_currency":"USD"}))
    monkeypatch.setattr(main,"hub",lambda:SimpleNamespace())
    monkeypatch.setattr(main,"_enrich_market_screener_item",lambda *_args:pytest.fail("Price-only alarms must not fetch financial reports"))
    return main._portfolio_alert_rows({"price_from_high_3y_percent","price_from_high_5y_percent"})[0]


def test_horizons_use_distinct_real_period_extremes_and_keep_1y_behavior(monkeypatch):
    ranges=_ranges();rows=_rows(monkeypatch,ranges)
    assert ranges["3y"]["state"]==ranges["5y"]["state"]=="ok"
    assert rows[0]["price_from_high_1y_percent"]==-20
    assert rows[0]["price_from_high_3y_percent"]==-60
    assert rows[0]["price_from_high_5y_percent"]==-80


def test_alarm_source_uses_authoritative_investment_accounts(monkeypatch):
    _rows(monkeypatch,_ranges())
    items=[]
    for key in ['investment','rsu','bank','pension','missing']:
        items.append({'holding':{'symbol':key.upper(),'account_id':key,'account_type':'Investment','asset_class':'EQUITY','currency':'USD','market_value':100},'price_ranges':_ranges()})
    monkeypatch.setattr(main,'local_store',SimpleNamespace(list_accounts=lambda:[{'id':'investment','type':'Investment'},{'id':'rsu','type':'ESOP'},{'id':'bank','type':'Bank'},{'id':'pension','type':'Long-Term Savings'},{'id':'missing'}]))
    monkeypatch.setattr(main,'_portfolio_alert_source_items',lambda:(items,'cached'))
    rows,_=main._portfolio_alert_rows({'price_from_high_3y_percent'})
    assert [row['symbol'] for row in rows]==['INVESTMENT']


@pytest.mark.parametrize("signal",["buy","sell"])
@pytest.mark.parametrize("period,operator,threshold,expected",[
    ("3y",">",-65,True),("3y","<",-65,False),
    ("5y","<",-75,True),("5y",">",-75,False),
    ("3y",">=",-60,True),("5y","<=",-80,True),
])
def test_saved_buy_sell_rules_evaluate_and_reload_selected_horizon(monkeypatch,tmp_path,signal,period,operator,threshold,expected):
    rows=_rows(monkeypatch,_ranges());store=AlertStore(tmp_path/"alerts.json")
    key=f"price_from_high_{period}_percent"
    rule=store.add_rule({"name":"Period fixture","signal":signal,"conditions":[{"metric":key,"operator":operator,"value":threshold}]})
    matches=store.evaluate(rows)[0]["matches"]
    assert bool(matches)==expected
    if matches:assert matches[0]["reasons"][0]["metric"]==key
    saved=AlertStore(store.path).list_rules()[0]
    assert saved["id"]==rule["id"] and saved["conditions"]==[{"metric":key,"operator":operator,"value":threshold}]


@pytest.mark.parametrize("state",["partial","missing",None])
def test_incomplete_long_history_is_unavailable_and_any_mode_keeps_other_conditions(monkeypatch,tmp_path,state):
    ranges=_ranges();ranges["5y"]["state"]=state
    rows=_rows(monkeypatch,ranges)
    assert rows[0]["price_from_high_5y_percent"] is None
    store=AlertStore(tmp_path/"alerts.json")
    missing={"metric":"price_from_high_5y_percent","operator":">","value":-100}
    store.add_rule({"name":"Only 5Y","conditions":[missing]})
    store.add_rule({"name":"Any","match_mode":"any","conditions":[missing,{"metric":"price_from_high_1y_percent","operator":">","value":-25}]})
    results=store.evaluate(rows)
    assert results[0]["matches"]==[] and results[0]["rule"]["last_missing_count"]==1
    assert results[1]["matches"][0]["missing_metrics"]==["price_from_high_5y_percent"]


def test_new_periods_are_localized_in_editor_guidance_reasons_and_saved_rule_text():
    root=Path(__file__).resolve().parents[1];source=(root/"web/app.js").read_text()
    functions=[]
    for name in ["t","alertMetric","alertMetricValue","alertMetricOptions","alertMetricGuidance","alertConditionGuidanceHtml","alertConditionText","alertReasonText"]:
        start=re.search(rf"^function {name}\(",source,re.M).start()
        end=re.search(r"^}",source[start:],re.M).end()
        functions.append(source[start:start+end])
    script="const window={};\n"+(root/"web/i18n.js").read_text()
    script+=source[source.index("const TRANSLATIONS ="):source.index("function locale(")]
    script+=source[source.index("const ALERT_METRIC_LOCALIZATIONS ="):source.index("const OPTION_LABELS =")]
    script+='\n'.join(functions)
    script+='\nconst state={language:"en",alertOptions:'+json.dumps(alert_rule_options())+'};'
    script+=r'''
const assert=require('node:assert/strict');const esc=value=>String(value);const fmt=value=>String(value);
for(const language of ['he','en','he']){
 state.language=language;
 for(const period of ['1y','3y','5y']){
  const key=`price_from_high_${period}_percent`;
  const metric=alertMetric(key);assert.equal(metric.unit,'%');
  assert.ok(alertMetricOptions(key).includes(`value="${key}" selected`));
  const condition=alertConditionText({metric:key,operator:'<',value:-20});
  const reason=alertReasonText({metric:key,operator:'>',value:-15,threshold:-20});
  assert.ok(condition.includes('-20%')&&reason.includes('-15%'));
  const text=condition+reason+alertConditionGuidanceHtml(key);
  if(language==='he'){assert.ok(/[א-ת]/.test(text));assert.ok(!/Price from|Current price|Values below|Incomplete history/.test(text));}
  else assert.ok(!/[א-ת]/.test(text));
 }
}
'''
    completed=subprocess.run(["node"],input=script,text=True,capture_output=True,cwd=root)
    assert completed.returncode==0,completed.stderr
