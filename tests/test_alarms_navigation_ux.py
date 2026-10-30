from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_alarms_popup_can_clear_visible_alarms_without_deleting_source_data():
    html = (ROOT / "web/index.html").read_text()
    script = (ROOT / "web/app.js").read_text()

    assert 'id="clearAlarms"' in html
    assert 'id="alarmsStatus" class="status-line" role="status" aria-live="polite"' in html
    assert 'const ALARM_DISMISSALS_STORAGE_KEY = "portfolioAnalyzer.alarmDismissals"' in script
    assert "function alarmDismissalId(alarm)" in script
    assert "function clearAlarms()" in script
    assert '$("clearAlarms").addEventListener("click", clearAlarms)' in script
    assert "New alarms will still appear." in script


def test_people_and_retirement_are_separate_navigation_groups_with_deep_links():
    html = (ROOT / "web/index.html").read_text()
    script = (ROOT / "web/app.js").read_text()

    assert '<span class="nav-menu-label">People</span>' in html
    assert ">Family Members</button>" in html
    assert ">Account Ownership</button>" in html
    assert '<span class="nav-menu-label">Retirement</span>' in html
    assert ">Pensions & Funds</button>" in html
    assert ">Retirement Projections</button>" in html
    assert html.index('<span class="nav-menu-label">People</span>') < html.index('<span class="nav-menu-label">Retirement</span>')
    assert 'data-modal-target="familyMembersSection" data-modal-focus="newFamilyMember"' in html
    assert 'data-modal-target="accountOwnershipSection" data-modal-focus="familyAttachAccount"' in html
    assert 'data-modal-target="simulatorPanel" data-modal-focus="simPersonSource"' in html
    assert 'id="familyMembersSection"' in html
    assert 'id="accountOwnershipSection"' in html
    assert 'id="accountOwnershipStatus" class="status-line" role="status" aria-live="polite"' in html
    assert 'id="simulatorPanel"' in html
    assert 'people: "People"' in script
    assert 'accountOwnership: "Account Ownership"' in script
    assert 'retirement: "Retirement"' in script
    assert 'pensionsFunds: "Pensions & Funds"' in script
    assert 'retirementProjections: "Retirement Projections"' in script
    assert "function focusModalDestination" in script
    assert "targetId: modalTrigger.dataset.modalTarget" in script
    assert "focusId: modalTrigger.dataset.modalFocus" in script
    assert '$("accountOwnershipStatus").textContent' in script
