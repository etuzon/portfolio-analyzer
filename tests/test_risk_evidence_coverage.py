"""Evidence coverage follows source semantics, exact identities and full weights."""
from copy import deepcopy
from datetime import date, timedelta

import httpx
import pytest

from app.local_portfolio import LocalPortfolioStore
from app.risk_input_sources import PublicRiskAPIs, SEC_TICKERS, extract_risk_records, extract_proposed_risk_records
from app.stress_risk_inputs import StressRiskInputs


def candidate(symbol="EXM", asset="EQUITY"):
    return {"security_key":symbol+"|YAHOO|USD","symbol":symbol,"stock_market":"YAHOO","currency":"USD",
        "name":"Example Corporation","issuer_name":"Example Corporation","asset_class":asset,
        "verified_issuer_domains":["example.com"],"has_open_position":True}


def source(body, **updates):
    return {"source_id":"source-1","url":"https://investor.example.com/report","retrieved_at":"2026-11-16T12:00:00Z",
        "observation_date":date.today().isoformat(),"text":"Example Corporation.\n"+body, **updates}


def fields(document, item=None):
    return {row["field"]:row for row in extract_risk_records(document,item or candidate())}


def test_yahoo_alias_resolves_one_actual_sec_ticker_exchange_and_preserves_it():
    def fetch(request):
        if str(request.url) == SEC_TICKERS:
            return httpx.Response(200,json={"fields":["cik","name","ticker","exchange"],
                "data":[[123,"Example Corporation","EXM","Nasdaq"]]})
        return httpx.Response(200,json={"cik":123,"name":"Example Corporation","tickers":["EXM"],
            "exchanges":["Nasdaq"],"addresses":{"business":{"stateOrCountry":"NY"}}})
    result=PublicRiskAPIs(transport=httpx.MockTransport(fetch)).fetch(candidate())
    assert result["status"] == "updated"
    issuer=next(row for row in result["records"] if row["field"] == "issuer_id")
    assert issuer["value"] == "sec:123"
    assert issuer["source_listing"] == {"ticker":"EXM","exchange":"NASDAQ"}


def test_yahoo_alias_rejects_ambiguous_sec_tickers_and_unpaired_exchange():
    index={"fields":["cik","name","ticker","exchange"],
        "data":[[123,"Example Corporation","EXM","Nasdaq"],[456,"Other Corporation","EXM","NYSE"]]}
    api=PublicRiskAPIs(transport=httpx.MockTransport(lambda _:httpx.Response(200,json=index)))
    assert api.fetch(candidate())["code"] == "source_identity_unavailable"
    index["data"].pop()
    def fetch(request):
        return httpx.Response(200,json=index if str(request.url) == SEC_TICKERS else
            {"cik":123,"name":"Example Corporation","tickers":["EXM","OTHER"],"exchanges":["NYSE","Nasdaq"]})
    assert not PublicRiskAPIs(transport=httpx.MockTransport(fetch)).fetch(candidate())["records"]


def test_multicurrency_table_is_not_renormalized_and_country_weights_are_not_collapsed():
    body="""Investment currency exposure
| Currency | Percent of portfolio |
| --- | --- |
| USD | 60% |
| EUR | 40% |

Economic country allocation
| Country | Percent of portfolio |
| --- | --- |
| United States | 60% |
| Israel | 40% |
"""
    result=fields(source(body))
    assert result["currency_exposures"]["value"] == {"USD":.6,"EUR":.4}
    assert result["currency_exposures"]["units"] == "fraction"
    assert result["country_exposures"]["value"] == {"US":.6,"IL":.4}
    assert "country_code" not in result
    assert "currency_exposures" not in fields(source(body.replace("40%","35%")))
    assert "currency_exposures" not in fields(source(body.replace("Investment currency exposure","Revenue currency breakdown")))


@pytest.mark.parametrize("title",["Historical investment currency exposure","Expected investment currency exposure",
    "Investment currency exposure excluding cash","Withdrawn investment currency allocation",
    "Retracted investment currency allocation","Superseded investment currency allocation"])
def test_qualified_currency_tables_do_not_become_complete_exposure(title):
    document=source(title+"\n| Currency | Percent |\n| USD | 100% |")
    assert "currency_exposures" not in fields(document)


@pytest.mark.parametrize("retraction",[
    "However, the allocation table above has been withdrawn and must not be used.",
    "The preceding table was superseded and is no longer valid.",
    "However, some of our investments are denominated in euros.",
])
def test_retracted_table_cannot_be_restored_by_selecting_only_its_rows(retraction):
    table="Investment currency allocation\n| Currency | Percent |\n| USD | 100% |"
    document=source(table+"\n\n"+retraction)
    assert "currency_exposures" not in fields(document)
    claim={"security_key":candidate()["security_key"],"source_id":"source-1","field":"currency_exposures",
        "value":{"USD":1},"as_of":date.today().isoformat(),"units":"fraction","evidence_quote":table}
    assert not extract_proposed_risk_records(document,candidate(),claim)


def test_non_us_whole_current_assertions_and_explicit_country_currency():
    result=fields(source("All our investments are denominated in euros.\nAll our investments are located in Israel.\nCountry currency: ILS"))
    assert result["currency_exposures"]["value"] == {"EUR":1}
    assert result["country_code"]["value"] == "IL"
    assert result["country_basis"]["value"] == "economic_exposure"
    assert result["country_currency"]["value"] == "ILS"
    assert not fields(source("All our investments are denominated in euros.",url="https://evil-example.com/report"))


def test_issuer_heading_without_punctuation_does_not_hide_its_next_assertion():
    document=source("All our investments are denominated in U.S. dollars.")
    document["text"]=document["text"].replace("Example Corporation.","Example Corporation")
    assert fields(document)["currency_exposures"]["value"] == {"USD":1}


def test_an_older_table_heading_does_not_inherit_the_newer_report_date():
    older=(date.today()-timedelta(days=365)).isoformat()
    document=source(f"Investment currency exposure {older}\n| Currency | Percent |\n| USD | 100% |")
    assert "currency_exposures" not in fields(document)


def test_fund_table_must_identify_this_exact_product_not_just_its_manager():
    fund=candidate("FUND_A","ETF")
    document=source("Fund: FUND_B\nComplete fund holdings\n| Identifier | Percent |\n| CHILD | 100% |")
    assert "fund_holdings" not in fields(document,fund)
    document["text"]=document["text"].replace("FUND_B","FUND_A")
    assert fields(document,fund)["fund_holdings"]["value"] == [{"identifier":"CHILD","weight":1}]


def bond_source():
    today=date.today().isoformat()
    maturity=(date.today()+timedelta(days=365)).isoformat()
    return source(f"""CUSIP: 91282CKD2
As of {today}
Instrument kind: sovereign bond
Maturity date: {maturity}
Fixed nominal noncallable: yes
Contractual payment currency: USD
Sovereign currency basis: local currency
Annual continuously compounded discount yield: 4.5%
Current credit spread: 75 basis points
Complete future contractual payment schedule including redemption
| Date | Amount |
| {maturity} | 104.5 |
""")


def test_bond_market_conventions_and_complete_schedule_keep_source_dates_and_units():
    item=candidate("91282CKD2","BOND")
    result=fields(bond_source(),item)
    assert result["continuous_yield"]["value"] == .045
    assert result["continuous_yield"]["units"] == "annual_continuous_decimal"
    assert result["current_spread_bps"]["value"] == 75
    assert result["currency_exposures"]["basis"] == "contractual_cashflow_currency"
    assert result["pricing_model"]["value"] == "cashflows_continuous"
    assert result["cashflows"]["value"][0]["amount"] == 104.5
    assert result["plain_nominal_noncallable"]["value"] is True
    wrong=candidate("88059ESH8","BOND")
    assert "continuous_yield" not in fields(bond_source(),wrong)
    ordinary=bond_source();ordinary["text"]=ordinary["text"].replace("Annual continuously compounded discount yield","Coupon rate")
    assert "continuous_yield" not in fields(ordinary,item)
    callable_doc=bond_source();callable_doc["text"] += "\nCallable: yes"
    result=fields(callable_doc,item)
    assert result["unsupported_bond"]["value"] is True
    assert "plain_nominal_noncallable" not in result and "pricing_model" not in result


def test_another_issues_terms_never_follow_a_cusip_mention():
    document=source("CUSIP 91282CKD2 is outstanding.\nCUSIP: 88059ESH8\nMaturity date: 2031-12-31\nCurrent credit spread: 999 basis points")
    # A prose reference is not a declared issue header. Even if a page contains
    # two genuine issue sections, each keeps its own exact terms.
    assert "current_spread_bps" not in fields(document,candidate("91282CKD2","BOND"))
    document["text"]=document["text"].replace("CUSIP 91282CKD2 is outstanding.","CUSIP: 91282CKD2\nCurrent credit spread: 100 basis points")
    assert fields(document,candidate("91282CKD2","BOND"))["current_spread_bps"]["value"] == 100
    assert fields(document,candidate("88059ESH8","BOND"))["current_spread_bps"]["value"] == 999


def test_nonfinite_numeric_literals_do_not_become_verified_bond_facts():
    document=bond_source();document["text"]=document["text"].replace("75 basis points","9"*1000+" basis points")
    assert "current_spread_bps" not in fields(document,candidate("91282CKD2","BOND"))


def test_grounded_model_claim_needs_correct_value_units_identity_quote_and_observation():
    item=candidate("91282CKD2","BOND");document=bond_source()
    claim={"security_key":item["security_key"],"source_id":"source-1","field":"continuous_yield","value":4.5,
        "as_of":date.today().isoformat(),"units":"annual_continuous_percent","evidence_quote":document["text"]}
    assert extract_proposed_risk_records(document,item,claim)[0]["value"] == .045
    for changed in ({"value":5.5},{"units":"percent"},{"source_id":"other"},{"security_key":"OTHER|YAHOO|USD"},
            {"evidence_quote":"Example Corporation. Invented annual continuous yield 4.5%."},
            {"as_of":(date.today()-timedelta(days=1)).isoformat()}):
        assert not extract_proposed_risk_records(document,item,{**claim,**changed})


def test_fund_members_resolve_their_own_evidence_without_manager_inheritance(tmp_path):
    store=LocalPortfolioStore(tmp_path/"fund.sqlite3")
    fund=candidate("FUND","ETF");child=candidate("CHILD")
    inventory=[fund,child]
    inputs=StressRiskInputs(store=lambda:store,inventory=lambda:inventory,credit=lambda _: {},sovereign=lambda _: {},countries=lambda _: {})
    document=source("Fund: FUND\nComplete fund holdings\n| Identifier | Percent |\n| CHILD | 60% |\n| UNKNOWN | 40% |")
    inputs.publish_evidence(fund,extract_risk_records(document,fund))
    before=inputs.read(fund)
    assert before["lookthrough_verified"] is True
    assert before["lookthrough_missing"] == ["UNKNOWN"]
    assert [row["weight"] for row in before["lookthrough"]] == [.6,.4]
    child_risk=before["lookthrough"][0]["item"]["stress_risk"]
    assert child_risk["issuer_id"] is None
    child_document=source("All our investments are denominated in U.S. dollars.")
    inputs.publish_evidence(child,extract_risk_records(child_document,child))
    after=inputs.read(fund)
    assert after["lookthrough"][0]["item"]["stress_risk"]["issuer_id"] is not None
    assert after["fingerprint"] != before["fingerprint"]
    assert after["lookthrough"][1]["item"]["stress_risk"]["error"] == "fund_underlying_inputs_missing"
    # No subset is expanded to a complete fund or assigned the manager's FX.
    incomplete=source("Fund: FUND\nComplete fund holdings\n| Identifier | Percent |\n| CHILD | 60% |")
    assert "fund_holdings" not in fields(incomplete,fund)
    zero=source("Fund: FUND\nComplete fund holdings\n| Identifier | Percent |\n| CHILD | 100% |\n| UNKNOWN | 0% |")
    inputs.publish_evidence(fund,extract_risk_records(zero,fund))
    zero_risk=inputs.read(fund)
    assert zero_risk["lookthrough_missing"] == []
    assert len(zero_risk["fund_holdings"]) == 2 and len(zero_risk["lookthrough"]) == 1


def test_old_fund_membership_and_cycles_stay_missing(tmp_path):
    store=LocalPortfolioStore(tmp_path/"cycle.sqlite3")
    fund=candidate("FUND","ETF")
    inputs=StressRiskInputs(store=lambda:store,inventory=lambda:[fund],credit=lambda _: {},sovereign=lambda _: {},countries=lambda _: {})
    document=source("Fund: FUND\nComplete fund holdings\n| Identifier | Percent |\n| FUND | 100% |")
    inputs.publish_evidence(fund,extract_risk_records(document,fund))
    assert inputs.read(fund)["lookthrough_missing"] == ["FUND"]
    old=deepcopy(document);old["observation_date"]=(date.today()-timedelta(days=46)).isoformat()
    other_store=LocalPortfolioStore(tmp_path/"old.sqlite3")
    other=StressRiskInputs(store=lambda:other_store,inventory=lambda:[fund],credit=lambda _: {},sovereign=lambda _: {},countries=lambda _: {})
    other.publish_evidence(fund,extract_risk_records(old,fund))
    assert "lookthrough" not in other.read(fund)
