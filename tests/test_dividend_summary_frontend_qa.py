"""Independent raw-fixture checks for displayed and exported dividend ordering."""
from tests.test_dividend_calendar_frontend import run_ui


def test_summary_missing_income_follows_known_income_across_currencies():
    run_ui(r'''
const raw=[{...a,id:'unknown-ils',symbol:'UNKNOWN',currency:'ILS',recorded_income:[]},
 {...a,id:'zero-ils',symbol:'ZERO',currency:'ILS',recorded_income:[{currency:'ILS',amount:0}]},
 {...a,id:'known-usd',symbol:'KNOWN',currency:'USD',recorded_income:[{currency:'USD',amount:10}]},
 {...a,id:'mixed',symbol:'MIXED',currency:'USD',recorded_income:[{currency:'ILS',amount:3},{currency:'USD',amount:4}]}];
dividendCalendarView.data={...data,assets:raw};
for(const direction of ['asc','desc']){
 dividendCalendarView.summary={query:'',currency:'',sort:'income',direction};
 assert.deepEqual(dividendSummaryRows().map(x=>x.symbol),['ZERO','KNOWN','UNKNOWN','MIXED']);
 assert.deepEqual(dividendSummaryCsvRows().slice(1).map(row=>row[0]),['ZERO · NASDAQ','KNOWN · NASDAQ','UNKNOWN · NASDAQ','MIXED · NASDAQ']);
}
assert.equal(raw[0].symbol,'UNKNOWN');
''')


def test_summary_monetary_sort_groups_native_currencies_and_keeps_zero_known():
    run_ui(r'''
dividendCalendarView.data={...data,assets:[{...a,id:'usd-high',symbol:'HIGH',price:1000},
 {...a,id:'usd-zero',symbol:'ZERO',price:0},
 {...a,id:'ils-low',symbol:'ILS',currency:'ILS',price:1},
 {...a,id:'unknown-ils',symbol:'UNKNOWN',currency:'ILS',price:null}]};
for(const [direction,expected] of [['asc',['ILS','ZERO','HIGH','UNKNOWN']],['desc',['ILS','HIGH','ZERO','UNKNOWN']]]){
 dividendCalendarView.summary={sort:'price',direction};assert.deepEqual(dividendSummaryRows().map(x=>x.symbol),expected);
}
dividendCalendarView.summary={query:' nasdaq ',currency:'USD',sort:'price',direction:'desc'};
assert.deepEqual(dividendSummaryRows().map(x=>x.symbol),['HIGH','ZERO']);
assert.equal(dividendSummaryCsvRows().length,3);
''')


def test_summary_pdf_failure_retains_filters_and_reports_localized_retry():
    run_ui(r'''
(async()=>{dividendCalendarView.data=data;dividendCalendarView.summary={query:'alpha',currency:'USD',sort:'yield',direction:'desc'};
$('dividendSummaryExportStatus').isConnected=true;globalThis.fetch=async()=>{throw Error('private transport failure')};
for(const language of ['en','he']){state.language=language;await exportDividendSummaryPdf();const status=$('dividendSummaryExportStatus').textContent;assert.ok(status);assert.ok(!status.includes('private transport'));if(language==='he')assert.ok(!/[A-Za-z]/.test(status));assert.equal(dividendCalendarView.summary.query,'alpha');assert.equal(dividendCalendarView.summary.direction,'desc');}
})();
''')
