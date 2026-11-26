"""Small in-place schema upgrade for databases created by version 1 (SQLite and PostgreSQL).

``create_all`` creates missing tables but never alters existing ones, so new columns are added here.
Version 1 stored ``external_inflow`` (+ = vehicles enter); version 2 stores ``net_demand``
(+ = vehicles leave), which is the same number with the opposite sign.
"""
from sqlalchemy import inspect, text

NEW_COLUMNS = {
    "networks": {"method": "VARCHAR(16) NOT NULL DEFAULT 'manual'", "map_meta": "JSON"},
    "junctions": {"lat": "FLOAT", "lng": "FLOAT", "node_type": "VARCHAR(16) NOT NULL DEFAULT 'junction'"},
    "roads": {"length_m": "FLOAT", "geometry": "JSON", "osm_way_id": "VARCHAR(32)",
              "highway": "VARCHAR(32) NOT NULL DEFAULT ''", "origin": "VARCHAR(8) NOT NULL DEFAULT 'user'"},
    "solutions": {"stale": "BOOLEAN NOT NULL DEFAULT FALSE"},
}


def upgrade(engine) -> list[str]:
    """Idempotent. Returns a description of the changes made."""
    done: list[str] = []
    with engine.begin() as conn:
        inspector = inspect(conn)
        tables = set(inspector.get_table_names())
        columns = {t: {c["name"] for c in inspector.get_columns(t)} for t in tables}
        if "junctions" in tables and "external_inflow" in columns["junctions"]:
            conn.execute(text("ALTER TABLE junctions RENAME COLUMN external_inflow TO net_demand"))
            conn.execute(text("UPDATE junctions SET net_demand = -net_demand WHERE net_demand <> 0"))
            done.append("junctions.external_inflow -> net_demand (sign flipped)")
        for table, new in NEW_COLUMNS.items():
            if table not in tables:
                continue
            for name, ddl in new.items():
                if name not in columns[table]:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
                    done.append(f"{table}.{name} added")
    return done
