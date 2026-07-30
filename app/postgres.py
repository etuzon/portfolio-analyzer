from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row


def connect_postgres(db_config: dict[str, Any]):
    sslmode = "require" if db_config.get("ssl") else "prefer"
    return psycopg.connect(
        host=db_config.get("host"),
        port=int(db_config.get("port", 5432)),
        dbname=db_config.get("database"),
        user=db_config.get("username"),
        password=db_config.get("password"),
        sslmode=sslmode,
        row_factory=dict_row,
        connect_timeout=5,
    )
