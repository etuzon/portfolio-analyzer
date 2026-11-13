"""History distinguishes real rating actions, detected observations and manual edits."""
from pathlib import Path

from test_holdings_credit_ratings_frontend import run_ui as run_summary_ui


ROOT = Path(__file__).resolve().parents[1]


def run_ui(body):
    setup = r'''
const event=(extra={})=>({event_id:'one',agency:'sp',origin:'public_ai',event_type:'rating_change',changed_fields:['rating'],
 previous_status:'rated',previous_rating:'BBB+',new_status:'rated',new_rating:'AA-',entity_name:'Example Company',scope:'issuer',scale:'global',term:'long_term',rating_type:'issuer',currency_basis:'foreign_currency',
 change_date:'2026-11-12',detected_at:'2026-11-13T09:00:00Z',date_basis:'agency_action',sources:[{url:'https://example.org/action',fetched_at:'2026-11-13T09:00:00Z'}],...extra});
'''
    run_summary_ui((ROOT / "web/credit-rating-history.js").read_text() + "\n" + setup + "\n" + body)


def test_table_shows_prior_to_new_native_grade_and_never_substitutes_detection_for_action_date():
    run_ui(r'''
for(const language of ['en','he']){
 state.language=language;const action=event();const html=creditRatingLatestChangeHtml({latest_change:action});
 assert.ok(html.includes('dir="ltr"'));assert.ok(html.includes('BBB+'));assert.ok(html.includes('AA-'));assert.ok(html.includes(' → '));
 assert.ok(html.includes(`${t('Changed')} 12/11/2026`));assert.ok(!html.includes(`${t('Changed')} 13/11/2026`));
 const detected=creditRatingLatestChangeHtml({latest_change:event({change_date:null,date_basis:'detected'})});
 assert.ok(detected.includes(`${t('Detected at')} 13/11/2026`));assert.ok(!detected.includes(`${t('Changed')} 13/11/2026`));
 const first=creditRatingLatestChangeHtml({latest_change:event({event_type:'first_observation',previous_status:null,previous_rating:null,date_basis:'detected',change_date:null})});
 assert.ok(first.includes(t('First recorded')));assert.ok(first.includes(t('Detected at')));assert.ok(!first.includes(' → '));
 if(language==='he')assert.ok(!/\b(?:Changed|Detected|First recorded)\b/.test(html+detected+first));else assert.ok(!/[א-ת]/.test(html+detected+first));
}
''')


def test_outlook_watch_events_name_the_signal_without_inventing_a_grade_transition():
    run_ui(r'''
const outlook=event({event_type:'outlook_change',changed_fields:['outlook'],previous_rating:'A-',new_rating:'A-',previous_outlook:'stable',new_outlook:'negative'});
assert.deepEqual(creditRatingHistoryChanges(outlook),[{label:'Outlook',previous:'Stable',current:'Negative'}]);
const watch=event({event_type:'watch_change',changed_fields:['watch'],previous_rating:'A-',new_rating:'A-',previous_watch:'unknown',new_watch:'negative'});
assert.deepEqual(creditRatingHistoryChanges(watch),[{label:'Watch',previous:'Unknown',current:'Negative'}]);
renderCreditRatingHistory({rating_history:[outlook,watch]});const html=$('securityCreditRatingHistoryList').innerHTML;
assert.ok(html.includes('Outlook'));assert.ok(html.includes('Watch'));assert.ok(!html.includes('BBB+'));assert.ok(!html.includes('>No watch<'));
''')


def test_manual_events_remain_explicit_and_have_manual_dates_actor_and_safe_sources():
    run_ui(r'''
for(const language of ['en','he']){
 state.language=language;
 const manual=event({origin:'manual',event_type:'manual_cleared',date_basis:'manual_entry',actor:'operator <unsafe>',change_date:'2020-01-01',sources:[{url:'javascript:alert(1)'},{url:'https://example.org/action'},{url:'https://example.org/action'}]});
 renderCreditRatingHistory({rating_history:[manual]});const html=$('securityCreditRatingHistoryList').innerHTML;
 assert.ok(html.includes(t('Manual override cleared')));assert.ok(html.includes(t('Manual entry date')));assert.ok(html.includes('13/11/2026'));assert.ok(!html.includes('01/01/2020'));
 assert.ok(html.includes(t('This records a manual edit, not an agency rating action.')));assert.ok(html.includes('operator &lt;unsafe&gt;'));assert.ok(!html.includes('javascript:'));assert.equal((html.match(/https:\/\/example.org\/action/g)||[]).length,1);
 const compact=creditRatingLatestChangeHtml({latest_change:manual});assert.ok(compact.includes(t('Manual override cleared')));assert.ok(!compact.includes(`${t('Changed')} `));
}
''')


def test_empty_and_initial_history_do_not_claim_backfilled_agency_changes():
    run_ui(r'''
renderCreditRatingHistory({rating_history:[]});assert.equal($('securityCreditRatingHistoryEmpty').hidden,false);assert.equal($('securityCreditRatingHistoryList').hidden,true);
assert.ok($('securityCreditRatingHistoryEmpty').textContent.includes('does not establish its earlier history'));
const first=event({event_type:'first_observation',changed_fields:['rating'],previous_status:null,previous_rating:null,date_basis:'detected',change_date:null});
renderCreditRatingHistory({rating_history:[first]});const html=$('securityCreditRatingHistoryList').innerHTML;assert.ok(html.includes('First recorded'));assert.ok(!html.includes(' → '));
assert.ok(html.includes('Rated entity'));assert.ok(html.includes('Issuer rating'));assert.ok(html.includes('Global scale'));assert.ok(html.includes('Long term'));assert.ok(html.includes('Foreign currency'));
''')
