"""Native agency grade movements remain distinct from observations and manual edits."""
from pathlib import Path

from test_holdings_credit_ratings_frontend import run_ui as run_summary_ui

ROOT = Path(__file__).resolve().parents[1]


def run_ui(body):
    run_summary_ui((ROOT / 'web/manual-credit-ratings.js').read_text() + '\n' +
                   (ROOT / 'web/credit-rating-history.js').read_text() + r'''
const opinion=(agency='sp',previous='BBB',rating='BBB+',extra={},changeExtra={})=>{
 const axes={agency,entity_name:'Example Corporation',scope:'issuer',scale:'global',term:'long_term',rating_type:'issuer',currency_basis:'foreign_currency'};
 return {...axes,status:'rated',rating,outlook:'unknown',watch:'unknown',latest_change:{...axes,origin:'public_ai',event_type:'rating_change',previous_status:'rated',previous_rating:previous,new_status:'rated',new_rating:rating,changed_fields:['rating'],date_basis:'agency_action',change_date:'2026-11-12',detected_at:'2026-11-13T09:00:00Z',...changeExtra},...extra};
};
''' + body)


def test_every_adjacent_native_grade_and_default_boundary_has_the_correct_direction():
    run_ui(r'''
for(const [agency,grades] of Object.entries(MANUAL_CREDIT_GRADES)){
 for(let index=1;index<grades.length;index++){
  assert.equal(holdingsCreditRatingTone(opinion(agency,grades[index],grades[index-1])),'upgrade',`${agency} ${grades[index]} to ${grades[index-1]}`);
  assert.equal(holdingsCreditRatingTone(opinion(agency,grades[index-1],grades[index])),'downgrade',`${agency} ${grades[index-1]} to ${grades[index]}`);
 }
 for(const grade of grades)assert.equal(holdingsCreditRatingTone(opinion(agency,grade,grade)),'unchanged');
}
for(const [agency,grade] of [['moodys','D'],['sp','RD'],['fitch','SD']])assert.equal(holdingsCreditRatingTone(opinion(agency,grade,MANUAL_CREDIT_GRADES[agency][0])),'unchanged');
''')


def test_only_matching_public_grade_changes_are_colored_as_movement():
    run_ui(r'''
for(const change of [
 {origin:'manual',event_type:'manual_added'},{origin:'manual',event_type:'manual_updated'},{origin:'manual',event_type:'manual_cleared'},
 {origin:'provider'},{origin:null},{event_type:'first_observation'},{event_type:'outlook_change'},{event_type:'watch_change'},
 {previous_status:'unavailable'},{new_status:'withdrawn'},{previous_rating:null},{previous_rating:'Unknown'},{new_rating:'AA'},
 {agency:'moodys'},{entity_name:'Example Bank Corporation'},{scope:'issue'},{scale:'national'},{term:'short_term'},
 {rating_type:'deposit'},{currency_basis:'local_currency'}
])assert.equal(holdingsCreditRatingTone(opinion('sp','BBB','BBB+',{},change)),'unchanged',JSON.stringify(change));
for(const record of [{primary_eligible:false},{manual_override:true},{source_kind:'manual'},{identity_verification:'user_entered'},{status:'not_found'},{rating:'AA'},{entity_name:null}])assert.equal(holdingsCreditRatingTone(opinion('sp','BBB','BBB+',record)),'unchanged');
assert.equal(holdingsCreditRatingTone(opinion('sp','BBB','BBB+',{entity_name:'Example Corp.'})),'upgrade','legal-form spelling is the same entity');
assert.equal(holdingsCreditRatingTone(opinion('sp','BBB','BBB+',{scope:'issue'},{scope:'issue'})),'unchanged','missing debt identity is not a comparable issue');
assert.equal(holdingsCreditRatingTone(opinion('sp','BBB','BBB+',{scope:'issue',isin:'US0000000001'},{scope:'issue',isin:'US0000000002'})),'unchanged');
assert.equal(holdingsCreditRatingTone(opinion('sp','BBB','BBB+',{scope:'issue',isin:'US0000000001'},{scope:'issue',isin:'US0000000001'})),'upgrade');
''')


def test_table_has_only_current_grades_and_tooltip_keeps_dates_transitions_and_manual_provenance():
    run_ui(r'''
for(const language of ['en','he']){
 state.language=language;
 const ratings=[opinion('moodys','A1','A2'),opinion('sp','BBB','BBB+'),opinion('fitch','A','A')];
 const entry={state:'ready',context:context('ACME','A2',{ratings})};
 const html=holdingsCreditRatingsContent(entry);
 assert.ok(html.includes('holding-credit-grade-downgrade'));assert.ok(html.includes('holding-credit-grade-upgrade'));assert.ok(html.includes('holding-credit-grade-unchanged'));
 assert.ok(!html.includes('data-credit-latest-change'));assert.ok(!html.includes('First recorded'));assert.ok(!html.includes('12/11/2026'));assert.ok(!html.includes(' → '));
 const description=holdingsCreditRatingsDescription(entry,'ACME');
 assert.ok(description.includes('A1 → A2'));assert.ok(description.includes('BBB → BBB+'));assert.ok(description.includes(`${t('Agency action date')}: 12/11/2026`));assert.ok(description.includes(`${t('Detected at')}: 13/11/2026`));
 assert.ok(description.includes(t('Agency rating upgraded')));assert.ok(description.includes(t('Agency rating downgraded')));
 const manual=opinion('sp','AA','BBB+',{}, {origin:'manual',event_type:'manual_cleared',actor:'Synthetic operator',date_basis:'manual_entry',change_date:null});
 const text=holdingsCreditRatingsDescription({state:'ready',context:context('ACME','BBB+',{ratings:[manual]})},'ACME');
 assert.ok(text.includes(t('Manual override cleared')));assert.ok(text.includes(t('Manual entry date')));assert.ok(text.includes('Synthetic operator'));assert.ok(text.includes(t('This records a manual edit, not an agency rating action.')));
 if(language==='he')assert.ok(!/Agency rating|No comparable|Manual entry|Detected at/.test(description+text));else assert.ok(!/[א-ת]/.test(description+text));
}
''')


def test_plain_text_descriptions_isolate_native_grades_without_forcing_rtl_statuses():
    run_ui(r'''
state.language='he';
for(const [agency,grade] of [['sp','AA-'],['fitch','BBB+'],['moodys','Aa2']]){
 const record=opinion(agency,grade,grade);
 assert.equal(holdingsCreditRatingDescriptionValue(record),`\u2066${grade}\u2069`);
 assert.ok(holdingsCreditRatingsDescription({state:'ready',context:{ratings:[record]}},'RTL').includes(`\u2066${grade}\u2069`));
}
for(const status of ['unrated','withdrawn','not_found','not_checked','unavailable','conflicting']){
 const value=holdingsCreditRatingDescriptionValue({status});
 assert.equal(value,holdingsCreditRatingStatus({status}));assert.ok(!value.includes('\u2066'));assert.ok(/[א-ת]/.test(value));
}
''')
