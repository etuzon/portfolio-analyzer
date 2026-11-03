from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def test_journal_shortcuts_require_authoritative_investment_account():
    script=(ROOT/'web/app.js').read_text()
    helper=script[script.index('function investmentJournalTrade('):script.index('function renderPositionTransactionHistory(')]
    body=r'''
const assert=require('node:assert/strict');
const state={localAccounts:[{id:'invest',type:'Investment'},{id:'esop',type:'ESOP'},{id:'bank',type:'Bank'},{id:'pension',type:'Long-Term Savings'},{id:'unknown'}]};
'''+helper+r'''
for(const action of ['BUY','SELL','SHORT']){
 assert.equal(investmentJournalTrade({action,account_db_id:'invest'}),true);
 assert.equal(investmentJournalTrade({action},'invest'),true);
 for(const id of ['esop','bank','pension','unknown','missing']){
  assert.equal(investmentJournalTrade({action,account_db_id:id,account_type:'Investment'},'invest'),false);
 }
}
assert.equal(investmentJournalTrade({action:'DIVIDEND',account_db_id:'invest'}),false);
state.localAccounts[0].type='ESOP';assert.equal(investmentJournalTrade({action:'BUY',account_db_id:'invest'}),false);
'''
    result=subprocess.run(['node'],input=body,text=True,capture_output=True)
    assert result.returncode==0,result.stderr
    position=script[script.index('function renderPositionTransactionHistory('):script.index('async function openPositionTransactionHistory(')]
    history=script[script.index('function renderTradeHistoryDetails('):script.index('function tradeHistoryCsvCell(')]
    assert 'investmentJournalTrade(tx)' in position
    assert 'investmentJournalTrade(tx, row.account_id)' in history
