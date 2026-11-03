"""Authoritative Investment-account view for investment portfolio analytics.

Account classification comes from the account record, never security metadata
or a caller-supplied holding label. Missing, archived and unknown classifications
do not establish membership. The underlying local records remain unchanged.
"""
from __future__ import annotations


class InvestmentStoreView:
    def __init__(self, store):
        self._store = store

    def __getattr__(self, name):
        return getattr(self._store, name)

    def list_accounts(self):
        return [row for row in self._store.list_accounts() if row.get("type") == "Investment"]

    def account_ids(self):
        return {row["id"] for row in self.list_accounts()}

    def holdings(self, *args, **kwargs):
        ids = self.account_ids()
        return [row for row in self._store.holdings(*args, **kwargs) if row.holding.account_id in ids]

    def list_transactions(self, *args, **kwargs):
        ids = self.account_ids()
        return [row for row in self._store.list_transactions(*args, **kwargs)
                if (row.get("account_db_id") or row.get("account_id")) in ids]

    def transaction_accounts(self):
        """Internal identity evidence to distinguish deleted and moved trades."""
        return {str(row.get("id")): row.get("account_db_id") or row.get("account_id")
                for row in self._store.list_transactions()}

    def list_funds(self, *args, **kwargs):
        ids = self.account_ids()
        return [row for row in self._store.list_funds(*args, **kwargs)
                if (row.get("account_db_id") or row.get("account_id")) in ids]

    def list_account_snapshots(self, *args, **kwargs):
        ids = self.account_ids()
        return [row for row in self._store.list_account_snapshots(*args, **kwargs)
                if (row.get("account_db_id") or row.get("account_id")) in ids]


def investments(store):
    return store if isinstance(store, InvestmentStoreView) else InvestmentStoreView(store)
