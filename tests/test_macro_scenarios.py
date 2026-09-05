import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def run_model(script: str) -> dict:
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_macro_scenario_compounds_each_parent_path() -> None:
    result = run_model(
        """
        const model = require('./web/scenario-model.js');
        const settings = model.normalizeSettings({
          priors: { increase: 0.40, decrease: 0.35, unchanged: 0.25 },
          localTrigger: 0.50,
        });
        const increase = model.calculateScenario('increase', settings);
        const decrease = model.calculateScenario('decrease', settings);
        const unchanged = model.calculateScenario('unchanged', settings);
        console.log(JSON.stringify({
          increaseConditional: increase.headline.conditional,
          increaseAbsolute: increase.headline.absolute,
          decreaseConditional: decrease.headline.conditional,
          decreaseAbsolute: decrease.headline.absolute,
          unchangedConditional: unchanged.headline.conditional,
          unchangedAbsolute: unchanged.headline.absolute,
          increasePath: model.pathTo('increase', 'inc_housing', settings).map((node) => node.id),
        }));
        """
    )

    assert result["increaseConditional"] == pytest.approx(0.163863)
    assert result["increaseAbsolute"] == pytest.approx(0.0655452)
    assert result["decreaseConditional"] == pytest.approx(0.17136)
    assert result["decreaseAbsolute"] == pytest.approx(0.059976)
    assert result["unchangedConditional"] == pytest.approx(0.455)
    assert result["unchangedAbsolute"] == pytest.approx(0.056875)
    assert result["increasePath"] == [
        "inc_treasury",
        "inc_nasdaq",
        "inc_dollar",
        "inc_tech",
        "inc_shekel",
        "inc_cpi",
        "inc_boi",
        "inc_housing",
    ]


def test_macro_scenario_keeps_sibling_outcomes_out_of_path_math() -> None:
    result = run_model(
        """
        const model = require('./web/scenario-model.js');
        const settings = model.defaultSettings();
        const increase = model.calculateScenario('increase', settings);
        const byId = Object.fromEntries(increase.nodes.map((node) => [node.id, node]));
        console.log(JSON.stringify({
          bank: byId.inc_banks.conditional,
          gold: byId.inc_gold.conditional,
          ai: byId.inc_ai.conditional,
          electricity: byId.inc_electricity.conditional,
          priorStatus: model.priorStatus(settings),
        }));
        """
    )

    assert result["bank"] == pytest.approx(0.1498176)
    assert result["gold"] == pytest.approx(0.585)
    assert result["ai"] == pytest.approx(0.54)
    assert result["electricity"] == pytest.approx(0.378)
    assert result["priorStatus"] == {"complete": False, "total": None, "valid": False}


def test_macro_scenario_rejects_invalid_trigger_distribution_for_absolute_math() -> None:
    result = run_model(
        """
        const model = require('./web/scenario-model.js');
        const settings = model.normalizeSettings({
          priors: { increase: 0.60, decrease: 0.60, unchanged: 0.20 },
          localTrigger: 0.50,
        });
        console.log(JSON.stringify({
          status: model.priorStatus(settings),
          absolute: model.calculateScenario('increase', settings).headline.absolute,
        }));
        """
    )

    assert result["status"]["complete"] is True
    assert result["status"]["valid"] is False
    assert result["status"]["total"] == pytest.approx(1.4)
    assert result["absolute"] is None


def test_macro_scenario_surface_is_localized_and_accessible() -> None:
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    translations = (ROOT / "web" / "i18n.js").read_text(encoding="utf-8")

    assert 'data-modal="macroScenarioModal"' in html
    assert 'aria-labelledby="macroScenarioTitle"' in html
    assert 'role="tablist" aria-label="Federal Reserve scenarios"' in html
    assert 'id="macroPriorStatus" class="status-line" role="status" aria-live="polite"' in html
    assert html.index('/scenario-model.js?v=0.9.4') < html.index('/app.js?v=0.9.4')
    assert 'macroScenarios: "תרחישי ארה״ב–ישראל"' in script
    assert "macroScenarios: state.macroScenarioSettings" in script
    assert "localStorage.setItem(MACRO_SCENARIO_STORAGE_KEY" in script
    assert '"Artificial intelligence": "בינה מלאכותית"' in translations
    assert '"Quantum computing": "מחשוב קוונטי"' in translations
    assert '"War sharply reduces tourism and aviation activity"' in translations


def test_every_scenario_node_and_group_has_a_hebrew_translation() -> None:
    scenarios = run_model(
        "const model = require('./web/scenario-model.js'); console.log(JSON.stringify(model.SCENARIOS));"
    )
    translations = (ROOT / "web" / "i18n.js").read_text(encoding="utf-8")
    labels = {"positive", "negative", "mixed"}
    for scenario in scenarios:
        labels.update({scenario["label"], scenario["triggerLabel"]})
        for node in scenario["nodes"]:
            labels.update({node["group"], node["label"]})

    missing = sorted(label for label in labels if f'"{label}":' not in translations)
    assert missing == []
