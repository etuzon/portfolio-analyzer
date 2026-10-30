"""Independent persisted-state tests for signal dismissal and cooldown settings."""
from datetime import datetime, timedelta, timezone

import pytest

from app import alerts, main
from app.alerts import AlertStore
from test_auth import _auth_environment, _change_password, _client, _login


@pytest.fixture
def dismissal_clock(monkeypatch):
    instant = [datetime(2026, 10, 30, 12, tzinfo=timezone.utc)]
    monkeypatch.setattr(alerts, "_now", lambda: instant[0].isoformat())
    return instant


def seed_rules(store):
    rules = []
    for name, signal in [("First buy", "buy"), ("Second buy", "buy"), ("Independent watch", "watch")]:
        rules.append(store.add_rule({"name": name, "signal": signal,
                                     "conditions": [{"metric": "current_ratio", "operator": ">", "value": 1}]}))
    return rules


ROWS = [{"symbol": "EXAMPLE", "current_ratio": 2}, {"symbol": "OTHER", "current_ratio": 2}]


def visible(store):
    return [(match["symbol"], match["signal"]) for rule in store.list_rules() for match in rule.get("last_matches", [])]


def test_dismissal_hides_same_pair_across_rules_and_persists_without_rewriting_history(tmp_path, dismissal_clock):
    path = tmp_path / "alerts.json"
    store = AlertStore(path)
    seed_rules(store)
    store.evaluate(ROWS)
    original_runs = store.list_runs()
    assert store.settings() == {"dismissal_days": 60}
    dismissed = store.dismiss_signal({"symbol": " example ", "signal": "buy"})
    assert dismissed["symbol"] == "EXAMPLE"
    assert datetime.fromisoformat(dismissed["expires_at"]) - datetime.fromisoformat(dismissed["dismissed_at"]) == timedelta(days=60)
    assert ("EXAMPLE", "buy") not in visible(store)
    assert ("EXAMPLE", "watch") in visible(store)
    assert visible(store).count(("OTHER", "buy")) == 2
    restored = AlertStore(path)
    assert restored.list_runs() == original_runs
    assert restored.list_dismissals() == [dismissed]
    assert visible(restored) == visible(store)
    restored.evaluate(ROWS)
    assert ("EXAMPLE", "buy") not in visible(restored)
    assert ("EXAMPLE", "watch") in visible(restored)


def test_default_cooldown_suppresses_until_exact_sixty_day_boundary(tmp_path, dismissal_clock):
    store = AlertStore(tmp_path / "alerts.json")
    seed_rules(store)
    start = dismissal_clock[0]
    store.dismiss_signal({"symbol": "EXAMPLE", "signal": "buy"})
    dismissal_clock[0] = start + timedelta(days=60) - timedelta(microseconds=1)
    store.evaluate(ROWS)
    assert ("EXAMPLE", "buy") not in visible(store)
    dismissal_clock[0] = start + timedelta(days=60)
    assert store.list_dismissals() == []
    store.evaluate(ROWS)
    assert visible(store).count(("EXAMPLE", "buy")) == 2


def test_settings_apply_to_new_dismissals_and_retry_does_not_extend_existing_expiry(tmp_path, dismissal_clock):
    path = tmp_path / "alerts.json"
    store = AlertStore(path)
    first = store.dismiss_signal({"symbol": "EXAMPLE", "signal": "buy"})
    store.save_settings({"dismissal_days": 7})
    dismissal_clock[0] += timedelta(days=1)
    assert store.dismiss_signal({"symbol": "EXAMPLE", "signal": "buy"}) == first
    second = store.dismiss_signal({"symbol": "OTHER", "signal": "buy"})
    assert second["days"] == 7
    assert datetime.fromisoformat(second["expires_at"]) - dismissal_clock[0] == timedelta(days=7)
    restored = AlertStore(path)
    assert restored.settings() == {"dismissal_days": 7}
    assert len(restored.list_dismissals()) == 2


@pytest.mark.parametrize("invalid", [0, -1, 3651, 1.2, True, False, "60", None])
def test_invalid_settings_do_not_replace_saved_default(tmp_path, invalid):
    store = AlertStore(tmp_path / "alerts.json")
    store.save_settings({"dismissal_days": 14})
    with pytest.raises(ValueError):
        store.save_settings({"dismissal_days": invalid})
    assert store.settings() == {"dismissal_days": 14}


def test_dismissal_api_returns_updated_visible_state_without_provider_calls(tmp_path, monkeypatch, dismissal_clock):
    store = AlertStore(tmp_path / "alerts.json")
    seed_rules(store)
    store.evaluate(ROWS)
    monkeypatch.setattr(main, "alert_store", store)
    monkeypatch.setattr(main, "scheduler", None)
    monkeypatch.setattr(main, "hub", lambda: pytest.fail("dismissal must not call market providers"))
    response = main.dismiss_alert_signal({"symbol": "EXAMPLE", "signal": "buy"})
    assert response["dismissed"] is True
    assert response["days"] == 60
    assert all((match["symbol"], match["signal"]) != ("EXAMPLE", "buy")
               for match in response["state"]["active_signals"])
    assert main.save_alert_settings({"dismissal_days": 3}) == {"dismissal_days": 3}
    with pytest.raises(main.HTTPException) as invalid:
        main.save_alert_settings({"dismissal_days": 0})
    assert invalid.value.status_code == 400


@pytest.mark.parametrize("role", ["Admin", "Operator", "Viewer"])
def test_new_signal_writes_enforce_roles_and_csrf(tmp_path, monkeypatch, role):
    auth = _auth_environment(tmp_path, monkeypatch)
    store = AlertStore(tmp_path / "alerts.json")
    monkeypatch.setattr(main, "alert_store", store)
    monkeypatch.setattr(main, "scheduler", None)
    auth.create_user({"first_name": "Synthetic", "last_name": "User", "username": "synthetic",
                      "password": "Initial-QA-Password", "role": role})
    anonymous = _client()
    assert anonymous.get("/api/settings/alerts").status_code == 401
    assert anonymous.post("/api/alerts/dismiss", json={"symbol": "EXAMPLE", "signal": "buy"}).status_code == 401
    client = _client()
    session = _change_password(client, _login(client, "synthetic", "Initial-QA-Password"),
                               "Initial-QA-Password", "Changed-QA-Password")
    assert client.get("/api/settings/alerts").status_code == 200
    expected = 403 if role == "Viewer" else 200
    for method, endpoint, payload in [(client.put, "/api/settings/alerts", {"dismissal_days": 7}),
                                       (client.post, "/api/alerts/dismiss", {"symbol": "EXAMPLE", "signal": "buy"})]:
        assert method(endpoint, json=payload).status_code == 403
        response = method(endpoint, headers={"X-CSRF-Token": session["csrf_token"]}, json=payload)
        assert response.status_code == expected, response.text
    if role == "Viewer":
        assert store.settings() == {"dismissal_days": 60}
        assert store.list_dismissals() == []
