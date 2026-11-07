import json
from datetime import date, timedelta

import pytest

from app.price_agent import (
    PriceAgent, PriceAgentError, RequestBudget, _public_address,
    make_rest_client, price_agent_settings,
)


DAY = (date.today() - timedelta(days=1)).isoformat()
SOURCE = "https://exchange.example/quote/AAPL"
TEXT = f"AAPL NASDAQ USD last quoted price 123.45 on {DAY}."
SECURITY = {"symbol": "AAPL", "stock_market": "NASDAQ", "currency": "USD", "location": "USA", "asset_class": "EQUITY", "quote_unit": "currency"}


def decision(name, arguments):
    return {"role": "assistant", "tool_calls": [{"id": "decision", "function": {"name": name, "arguments": json.dumps(arguments)}}]}


def item(**overrides):
    return {"price_input": 123.45, "price_date": DAY, "currency": "USD", "quote_unit": "currency", "price_basis": "last", "source_url": SOURCE, "observed_at": None, "evidence_quote": TEXT, **overrides}


class Rest:
    def __init__(self):
        self.calls = []
        self.rows = []

    def __call__(self, method, path, *, params=None, payload=None):
        self.calls.append((method, path, params, payload))
        if method == "PUT":
            self.rows = [{**row, "price": row["price_input"] / (100 if row["quote_unit"] in {"agorot", "cents"} else 1)} for row in payload["items"]]
            return {"updated": len(self.rows), "items": self.rows}
        return {"security": SECURITY, "current": None, "items": self.rows}


def agent_for(responses, rest=None, **settings):
    iterator = iter(responses)
    return PriceAgent(
        price_agent_settings({"price_agent": settings}), rest or Rest(),
        model=lambda *_: next(iterator),
        search=lambda _: [{"url": SOURCE, "title": "Exchange quote", "description": "Search snippet"}],
        fetch=lambda _: TEXT,
    )


def research_then_submit(observation=None):
    return [decision("search_web", {"query": "AAPL NASDAQ current price USD"}), decision("read_source", {"url": SOURCE}), decision("submit_prices", {"items": [observation or item()]})]


def test_update_researches_writes_and_verifies_once_with_separate_budgets():
    rest = Rest()
    agent = agent_for(research_then_submit(), rest)
    result = agent.run("AAPL", "NASDAQ")
    assert result["status"] == "updated"
    assert result["model_calls"] == 3
    assert result["rest_calls"] == 3
    assert result["web_calls"] == 2
    assert [call[0] for call in rest.calls] == ["GET", "PUT", "GET"]
    assert rest.calls[0][2]["date_from"] == rest.calls[0][2]["date_to"] == date.today().isoformat()
    assert rest.calls[2][2]["date_from"] == rest.calls[2][2]["date_to"] == DAY
    written = rest.calls[1][3]["items"][0]
    assert written["price_input"] == 123.45
    assert written["source_url"] == SOURCE
    assert written["retrieved_at"]
    assert written["observed_at"] is None
    assert written["evidence_quote"] == TEXT
    with pytest.raises(PriceAgentError, match="already run"):
        agent.run("AAPL", "NASDAQ")
    assert len(rest.calls) == 3


def test_dry_run_researches_without_writing():
    rest = Rest()
    agent = agent_for(research_then_submit(), rest)
    result = agent.run("AAPL", "NASDAQ", dry_run=True)
    assert result["status"] == "dry_run"
    assert result["proposal"]["items"][0]["price_input"] == 123.45
    assert result["rest_calls"] == len(rest.calls) == 1


def test_model_hard_ceiling_counts_failed_tool_decisions_and_cannot_be_raised():
    rest = Rest()
    requests = []
    agent = PriceAgent(price_agent_settings({"price_agent": {"max_model_calls": 999, "max_rest_calls": 999}}), rest,
                       model=lambda *_: requests.append(True) or decision("arbitrary_url", {}))
    with pytest.raises(PriceAgentError, match="model call limit"):
        agent.run("AAPL", "NASDAQ")
    assert len(requests) == agent.budget.model_calls == 8
    assert agent.budget.rest_calls == len(rest.calls) == 1
    assert not rest.rows


def test_failed_internet_calls_consume_budget_and_do_not_enable_a_write():
    agent = agent_for([decision("search_web", {"query": "AAPL"})] * 8)
    def failed(_query):
        raise PriceAgentError("Search unavailable")
    agent.search = failed
    with pytest.raises(PriceAgentError, match="model call limit"):
        agent.run("AAPL", "NASDAQ")
    assert agent.budget.model_calls == agent.budget.web_calls == 8
    assert agent.budget.rest_calls == 1


def test_failed_write_is_terminal_and_never_retried():
    rest = Rest()
    def failing(method, path, **kwargs):
        if method == "PUT":
            rest.calls.append((method, path, None, kwargs.get("payload")))
            raise PriceAgentError("Timeout")
        return rest(method, path, **kwargs)
    agent = agent_for(research_then_submit() + [decision("submit_prices", {"items": [item()]})] * 2, failing)
    with pytest.raises(PriceAgentError, match="outcome is unknown"):
        agent.run("AAPL", "NASDAQ")
    assert [call[0] for call in rest.calls] == ["GET", "PUT"]
    assert agent.budget.rest_calls == 2
    assert agent.budget.model_calls == 3


def test_failed_verification_reports_written_unverified_and_does_not_retry():
    rest = Rest()
    def failing(method, path, **kwargs):
        if method == "GET" and rest.rows:
            rest.calls.append((method, path, None, None))
            raise PriceAgentError("Timeout")
        return rest(method, path, **kwargs)
    agent = agent_for(research_then_submit(), failing)
    result = agent.run("AAPL", "NASDAQ")
    assert result["status"] == "written_unverified"
    assert result["rest_calls"] == 3
    assert [call[0] for call in rest.calls] == ["GET", "PUT", "GET"]


@pytest.mark.parametrize("tamper", ["price", "source_url", "quote_unit", "price_basis", "evidence_quote"])
def test_verification_detects_wrong_normalization_or_replaced_source_evidence(tamper):
    rest = Rest()
    def replaced(method, path, **kwargs):
        result = rest(method, path, **kwargs)
        if method == "GET" and rest.rows:
            result["items"][0][tamper] = 9999 if tamper == "price" else "changed"
        return result
    agent = agent_for(research_then_submit(), replaced)
    result = agent.run("AAPL", "NASDAQ")
    assert result["status"] == "written_unverified"
    assert result["rest_calls"] == 3


def test_insufficient_rest_budget_never_writes_an_unverifiable_batch():
    rest = Rest()
    responses = research_then_submit() + [{"role": "assistant", "content": "A larger REST budget is needed."}]
    agent = agent_for(responses, rest, max_rest_calls=2)
    result = agent.run("AAPL", "NASDAQ")
    assert result["status"] == "not_updated"
    assert [call[0] for call in rest.calls] == ["GET"]


@pytest.mark.parametrize("bad_item", [
    item(price_input=-1), item(price_input=True), item(price_input=float("inf")), item(price_input=10**400), item(price_input=1234),
    item(currency="ILS"), item(quote_unit="agorot"), item(price_basis="adjusted_close"),
    item(price_date=(date.today() + timedelta(days=1)).isoformat()),
    item(source_url="https://unfetched.example/quote"), item(evidence_quote="Invented quote 123.45"),
    item(observed_at=DAY + "T12:00:00"), item(observed_at="1999-01-01T12:00:00+00:00"),
])
def test_invalid_or_unsupported_price_evidence_never_writes(bad_item):
    rest = Rest()
    agent = agent_for(research_then_submit(bad_item) + [{"role": "assistant", "content": "The price was not verified."}], rest)
    result = agent.run("AAPL", "NASDAQ")
    assert result["status"] == "not_updated"
    assert [call[0] for call in rest.calls] == ["GET"]


def test_snippets_without_fetched_evidence_cannot_support_a_write():
    responses = [decision("search_web", {"query": "AAPL"}), decision("submit_prices", {"items": [item()]}), {"role": "assistant", "content": "Missing fetched evidence."}]
    rest = Rest()
    result = agent_for(responses, rest).run("AAPL", "NASDAQ")
    assert result["status"] == "not_updated"
    assert len(rest.calls) == 1


def test_price_date_must_be_demonstrated_by_the_actual_price_excerpt():
    rest = Rest()
    mismatched = item(price_date=(date.today() - timedelta(days=5)).isoformat(), evidence_quote="last quoted price 123.45")
    responses = research_then_submit(mismatched) + [{"role": "assistant", "content": "Actual price date missing."}]
    assert agent_for(responses, rest).run("AAPL", "NASDAQ")["status"] == "not_updated"
    assert len(rest.calls) == 1


@pytest.mark.parametrize("evidence,extra", [
    (f"AAPL NASDAQ USD Adjusted Close 123.45 on {DAY}", {"price_basis": "close"}),
    (f"AAPL NASDAQ USD AdjustedClose 123.45 on {DAY}", {"price_basis": "close"}),
    (f"AAPL NASDAQ USD NAV Close 123.45 on {DAY}", {"price_basis": "close"}),
    (f"AAPL NASDAQ USD Net Asset Value Close 123.45 on {DAY}", {"price_basis": "close"}),
    (f"AAPL NASDAQ USD Redemption price Close 123.45 on {DAY}", {"price_basis": "close"}),
    (f"AAPL NASDAQ USD Purchase price Close 123.45 on {DAY}", {"price_basis": "close"}),
    (f"AAPL NASDAQ USD Last 123.45 percent of par on {DAY}", {}),
    (f"AAPL NASDAQ USD Last 123.45% on {DAY}", {}),
    (f"AAPL NASDAQ USD Last 123.45 on {DAY}", {"observed_at": DAY + "T12:34:56+00:00"}),
    (f"AAPL NASDAQ USD Last 123.45 on {DAY}. Dividend declared on {DAY}T12:34:56+00:00", {"observed_at": DAY + "T12:34:56+00:00"}),
    (f"AAPL NASDAQ USD Last 123.45 on 1999-01-01. Dividend declared on {DAY}", {}),
    (f"AAPL NASDAQ USD Last 123.45. Dividend declared on {DAY}", {}),
    (f"AAPL NASDAQ USD Close 100.00 on 2020-01-01; Last 123.45 on {DAY}", {"price_input": 100.0, "price_basis": "close"}),
    (f"AAPL NASDAQ USD Close 123.45 on {DAY}", {"price_basis": "last"}),
])
def test_basis_timestamps_and_other_event_dates_cannot_be_invented_or_relabelled(evidence, extra):
    rest = Rest()
    agent = agent_for(research_then_submit(item(evidence_quote=evidence, **extra)) + [{"role": "assistant", "content": "Evidence cannot support this proposal."}], rest)
    agent.fetch = lambda _: evidence
    result = agent.run("AAPL", "NASDAQ")
    assert result["status"] == "not_updated"
    assert [call[0] for call in rest.calls] == ["GET"]


def test_cropping_adjusted_qualifier_from_excerpt_does_not_make_raw_close_evidence():
    evidence = f"AAPL NASDAQ USD Adjusted Close 123.45 on {DAY}"
    rest = Rest()
    agent = agent_for(research_then_submit(item(evidence_quote=f"Close 123.45 on {DAY}", price_basis="close")) + [{"role": "assistant", "content": "Adjusted evidence rejected."}], rest)
    agent.fetch = lambda _: evidence
    assert agent.run("AAPL", "NASDAQ")["status"] == "not_updated"
    assert [call[0] for call in rest.calls] == ["GET"]


@pytest.mark.parametrize("basis,label", [("last", "Last"), ("close", "Unadjusted Close")])
def test_actual_literal_observation_timestamp_and_matching_raw_basis_are_accepted(basis, label):
    observed = DAY + "T12:34:56+00:00"
    evidence = f"AAPL NASDAQ USD {label} 123.45 on {observed}"
    agent = agent_for(research_then_submit(item(evidence_quote=evidence, observed_at=observed, price_basis=basis)))
    agent.fetch = lambda _: evidence
    assert agent.run("AAPL", "NASDAQ", dry_run=True)["status"] == "dry_run"


def test_history_can_submit_separate_dated_row_excerpts_from_one_source_page():
    prior = (date.today() - timedelta(days=2)).isoformat()
    first = f"Last 120.00 on {prior}"
    second = f"Last 123.45 on {DAY}"
    text = f"AAPL NASDAQ USD. {first}. {second}."
    rows = [item(price_input=120.0, price_date=prior, evidence_quote=first), item(evidence_quote=second)]
    responses = research_then_submit()[:2] + [decision("submit_prices", {"items": rows})]
    rest = Rest()
    agent = agent_for(responses, rest)
    agent.fetch = lambda _: text
    result = agent.run("AAPL", "NASDAQ", date_from=prior, date_to=DAY)
    assert result["status"] == "updated"
    assert [row["price_date"] for row in result["items"]] == [prior, DAY]
    assert [call[0] for call in rest.calls] == ["GET", "PUT", "GET"]


@pytest.mark.parametrize("text", [
    "AAPL NASDAQ USD profile. MSFT Close 123.45 on {day}",
    "AAPL NASDAQ USD profile | MSFT Close 123.45 on {day}",
    "AAPL NASDAQ USD profile, MSFT Close 123.45 on {day}",
    "AAPL NASDAQ USD Close EUR 123.45 on {day}",
    "AAPL NASDAQ USD Close 123.45 on {day} in euros",
    "AAPL NASDAQ USD Close 123.45 on {day} in Canadian dollars",
])
def test_cli_current_price_shares_listing_and_currency_evidence_guards(text):
    text = text.format(day=DAY)
    rest = Rest()
    agent = agent_for(research_then_submit(item(price_basis="close", evidence_quote=text)) +
                      [{"role": "assistant", "content": "The observation could not be verified."}], rest)
    agent.fetch = lambda _: text
    assert agent.run("AAPL", "NASDAQ")["status"] == "not_updated"
    assert [call[0] for call in rest.calls] == ["GET"]


@pytest.mark.parametrize("conflicting_currency", [False, True])
def test_explicit_old_history_keeps_source_header_binding_and_shared_currency_guard(conflicting_currency):
    old_day = (date.today() - timedelta(days=100)).isoformat()
    row = f"Close 123.45 on {old_day}" + (" in euros" if conflicting_currency else "")
    text = "AAPL NASDAQ USD. " + row
    rest = Rest()
    agent = agent_for(research_then_submit(item(price_basis="close", price_date=old_day, evidence_quote=row)) +
                      [{"role": "assistant", "content": "The observation could not be verified."}], rest)
    agent.fetch = lambda _: text
    result = agent.run("AAPL", "NASDAQ", date_from=old_day, date_to=old_day)
    assert result["status"] == ("not_updated" if conflicting_currency else "updated")
    assert [call[0] for call in rest.calls] == (["GET"] if conflicting_currency else ["GET", "PUT", "GET"])


@pytest.mark.parametrize("row_prefix", ["MSFT NASDAQ USD", "MSFT", "Ticker: MSFT", "NASDAQ: MSFT", "AAPL NYSE USD"])
def test_history_source_header_cannot_override_explicit_other_listing_in_row(row_prefix):
    old_day = (date.today() - timedelta(days=100)).isoformat()
    row = f"{row_prefix} Close 123.45 on {old_day}"
    rest = Rest()
    agent = agent_for(research_then_submit(item(price_basis="close", price_date=old_day, evidence_quote=row)) +
                      [{"role": "assistant", "content": "The row identifies a different listing."}], rest)
    agent.fetch = lambda _: "AAPL NASDAQ USD profile. " + row
    assert agent.run("AAPL", "NASDAQ", date_from=old_day, date_to=old_day)["status"] == "not_updated"
    assert [call[0] for call in rest.calls] == ["GET"]


@pytest.mark.parametrize("rendered_day", [
    DAY,
    (date.today() - timedelta(days=1)).strftime("%d %B %Y"),
    (date.today() - timedelta(days=1)).strftime("%B %d, %Y"),
    (date.today() - timedelta(days=1)).strftime("%b %d, %Y"),
])
def test_supported_evidence_dates_and_trailing_price_punctuation_are_accepted(rendered_day):
    text = f"AAPL NASDAQ USD Last 123.45. Observed {rendered_day}."
    agent = agent_for(research_then_submit(item(evidence_quote=text)))
    agent.fetch = lambda _: text
    result = agent.run("AAPL", "NASDAQ", dry_run=True)
    assert result["status"] == "dry_run"
    assert result["proposal"]["items"][0]["evidence_quote"] == text


@pytest.mark.parametrize("day,source_day", [("2026-06-16", "16/06/2026"), ("2026-06-06", "06/06/2026")])
def test_unambiguous_day_month_source_dates_are_supported(day, source_day):
    text = f"AAPL NASDAQ USD Last 123.45 on {source_day}"
    agent = agent_for(research_then_submit(item(price_date=day, evidence_quote=text)))
    agent.fetch = lambda _: text
    assert agent.run("AAPL", "NASDAQ", dry_run=True)["status"] == "dry_run"


@pytest.mark.parametrize("claimed_day", ["2026-06-11", "2026-11-06"])
def test_ambiguous_numeric_source_date_is_rejected_regardless_of_model_interpretation(claimed_day):
    text = "AAPL NASDAQ USD Last 123.45 on 11/06/2026"
    rest = Rest()
    agent = agent_for(research_then_submit(item(price_date=claimed_day, evidence_quote=text)) + [{"role": "assistant", "content": "Ambiguous source date."}], rest)
    agent.fetch = lambda _: text
    assert agent.run("AAPL", "NASDAQ")["status"] == "not_updated"
    assert [call[0] for call in rest.calls] == ["GET"]


@pytest.mark.parametrize("source_price,claimed_price", [
    ("123,45", 12345), ("123,45", 123), ("1,23,456", 123456),
    ("1,234,56", 123456), ("1.234,50", 1234.5), ("123.45.6", 123.45),
])
def test_malformed_or_comma_decimal_evidence_cannot_change_the_price_scale(source_price, claimed_price):
    text = f"AAPL NASDAQ USD Last {source_price} on {DAY}"
    rest = Rest()
    agent = agent_for(research_then_submit(item(price_input=claimed_price, evidence_quote=text)) + [{"role": "assistant", "content": "Unsupported numeric price format."}], rest)
    agent.fetch = lambda _: text
    assert agent.run("AAPL", "NASDAQ")["status"] == "not_updated"
    assert [call[0] for call in rest.calls] == ["GET"]


@pytest.mark.parametrize("source_price,claimed_price", [("1,234.50", 1234.5), ("1,234,567.50", 1234567.5), ("1234.50", 1234.5)])
def test_plain_decimal_and_proper_thousands_groups_remain_supported(source_price, claimed_price):
    text = f"AAPL NASDAQ USD Last {source_price}. Observed {DAY}"
    agent = agent_for(research_then_submit(item(price_input=claimed_price, evidence_quote=text)))
    agent.fetch = lambda _: text
    assert agent.run("AAPL", "NASDAQ", dry_run=True)["status"] == "dry_run"


@pytest.mark.parametrize("text", [
    f"OTHER NASDAQ USD Last 123.45 on {DAY}",
    f"AAPL NYSE USD Last 123.45 on {DAY}",
    f"AAPL NASDAQ EUR Last 123.45 on {DAY}",
    f"AAPL NASDAQ USD {DAY}",
])
def test_source_must_establish_listing_market_currency_and_labelled_price(text):
    agent = agent_for(research_then_submit(item(evidence_quote=text)) + [{"role": "assistant", "content": "Incompatible evidence."}])
    agent.fetch = lambda _: text
    assert agent.run("AAPL", "NASDAQ")["status"] == "not_updated"
    assert agent.budget.rest_calls == 1


def test_date_year_cannot_be_used_as_a_price():
    text = f"AAPL NASDAQ USD Last observed {DAY}"
    agent = agent_for(research_then_submit(item(price_input=date.today().year, evidence_quote=text)) + [{"role": "assistant", "content": "Missing price."}])
    agent.fetch = lambda _: text
    assert agent.run("AAPL", "NASDAQ")["status"] == "not_updated"


@pytest.mark.parametrize("scaled_unit", ["agorot", "cents"])
@pytest.mark.parametrize("declared", [True, False])
def test_scaled_price_source_must_declare_the_actual_quote_unit(scaled_unit, declared):
    if scaled_unit == "agorot":
        security = {"symbol": "1159492", "stock_market": "TASE", "currency": "ILS", "location": "Israel", "asset_class": "EQUITY", "quote_unit": "agorot"}
    else:
        security = {**SECURITY, "asset_class": "BOND", "quote_unit": "cents"}
    text = f"{security['symbol']} {security['stock_market']} {security['currency']} Last 123.45 {'in ' + scaled_unit if declared else ''} on {DAY}"
    def rest(_method, _path, **_kwargs):
        return {"security": security, "items": [], "current": None}
    observation = item(currency=security["currency"], quote_unit=scaled_unit, evidence_quote=text)
    agent = agent_for(research_then_submit(observation) + [{"role": "assistant", "content": "Quote units unknown."}], rest)
    agent.fetch = lambda _: text
    result = agent.run(security["symbol"], security["stock_market"], dry_run=True)
    assert result["status"] == ("dry_run" if declared else "not_updated")
    assert agent.budget.rest_calls == 1


def test_model_cannot_fetch_a_source_not_returned_by_search():
    fetched = []
    agent = agent_for([decision("read_source", {"url": "https://arbitrary.example"}), {"role": "assistant", "content": "Unknown."}])
    agent.fetch = lambda url: fetched.append(url) or "123.45"
    result = agent.run("AAPL", "NASDAQ")
    assert result["status"] == "not_updated"
    assert not fetched


def test_historical_request_rejects_out_of_range_prices_without_writing():
    earlier = (date.today() - timedelta(days=5)).isoformat()
    rest = Rest()
    agent = agent_for(research_then_submit() + [{"role": "assistant", "content": "Requested date unavailable."}], rest)
    result = agent.run("AAPL", "NASDAQ", date_from=earlier, date_to=earlier)
    assert result["status"] == "not_updated"
    assert rest.calls[0][2]["date_from"] == earlier
    assert len(rest.calls) == 1


@pytest.mark.parametrize("history", [False, True])
def test_older_evidence_cannot_replace_a_newer_current_price_but_can_fill_history(history):
    prior = (date.today() - timedelta(days=2)).isoformat()
    text = f"AAPL NASDAQ USD Last 123.45 on {prior}"
    rest = Rest()
    def with_current(method, path, **kwargs):
        response = rest(method, path, **kwargs)
        response["current"] = {"price_date": DAY, "price": 125.0}
        return response
    responses = research_then_submit(item(price_date=prior, evidence_quote=text)) + [{"role": "assistant", "content": "Only stale source evidence was available."}]
    agent = agent_for(responses, with_current)
    agent.fetch = lambda _: text
    args = {"date_from": prior, "date_to": prior} if history else {}
    result = agent.run("AAPL", "NASDAQ", **args)
    assert result["status"] == ("updated" if history else "not_updated")
    assert [call[0] for call in rest.calls] == (["GET", "PUT", "GET"] if history else ["GET"])
    assert rest.calls[0][2]["date_from"] == (prior if history else date.today().isoformat())


def test_settings_select_codex_or_claude_and_do_not_raise_hard_budgets():
    assert price_agent_settings({})["provider"] == "codex"
    assert price_agent_settings({})["model"] == "gpt-6.1-sol"
    settings = price_agent_settings({"price_agent": {"provider": "claude", "max_model_calls": 99, "max_rest_calls": 99, "max_web_calls": 99}})
    assert settings["model"] == "sonnet"
    assert settings["reasoning_effort"] == "medium"
    assert settings["max_model_calls"] == settings["max_rest_calls"] == settings["max_web_calls"] == 8
    with pytest.raises(PriceAgentError):
        price_agent_settings({"price_agent": {"provider": "other"}})


@pytest.mark.parametrize("url", ["http://example.com", "https://user:password@example.com", "https://example.com:8443", "https://example.com/#fragment"])
def test_evidence_url_rejects_unsafe_origin_forms(url):
    with pytest.raises(PriceAgentError):
        _public_address(url)


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.2", "169.254.169.254", "::1", "::ffff:127.0.0.1"])
def test_evidence_cannot_resolve_to_local_addresses(monkeypatch, address):
    monkeypatch.setattr("app.price_agent.socket.getaddrinfo", lambda *_args, **_kwargs: [(None, None, None, None, (address, 443))])
    with pytest.raises(PriceAgentError, match="local or private"):
        _public_address("https://attacker.example/")


def test_public_source_returns_checked_address_for_pinning(monkeypatch):
    monkeypatch.setattr("app.price_agent.socket.getaddrinfo", lambda *_args, **_kwargs: [(None, None, None, None, ("8.8.8.8", 443))])
    parsed, address = _public_address("https://example.com/quote")
    assert parsed.hostname == "example.com"
    assert address == "8.8.8.8"


def test_rest_client_requires_explicit_auth_and_https():
    with pytest.raises(PriceAgentError, match="TOKEN"):
        make_rest_client("https://localhost:6443", "")
    with pytest.raises(PriceAgentError, match="HTTPS"):
        make_rest_client("http://localhost:6443", "test-token")


def test_raw_budget_still_cannot_allow_ninth_attempt():
    budget = RequestBudget(model_limit=99, rest_limit=99, web_limit=99)
    for _ in range(8):
        budget.consume("model")
        budget.consume("rest")
        budget.consume("web")
    with pytest.raises(PriceAgentError):
        budget.consume("model")
    with pytest.raises(PriceAgentError):
        budget.consume("rest")
    with pytest.raises(PriceAgentError):
        budget.consume("web")
    assert budget.model_calls == budget.rest_calls == budget.web_calls == 8
    assert budget.counts()["max_web_calls"] == 8
