import os
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, declarative_base

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv("FIRE_ALARM_DB", os.path.join(BASE_DIR, "fire_alarm.db"))


def _sqlite_pragmas(dbapi_connection, connection_record):
    """每次建立 SQLite 连接时开启外键、写超时与 WAL（:memory: 下 WAL 自动忽略）。"""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA journal_mode=WAL")
    finally:
        cursor.close()


engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False, "timeout": 30},
)
event.listen(engine, "connect", _sqlite_pragmas)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 轻量迁移：为旧库补齐新增字段（PRAGMA table_info 判断 -> ALTER TABLE ADD COLUMN）
_MIGRATIONS = {
    "users": [
        ("is_active", "BOOLEAN DEFAULT 1"),
    ],
    "plans": [
        ("created_by", "INTEGER"),
    ],
    "drills": [
        ("duration", "INTEGER"),
    ],
}

# 防御性唯一索引：既有库先剔除重复（保留最早一条）再建索引，全程幂等。
_UNIQUE_INDEX_RULES = [
    (
        "emergencies",
        "alarm_id",
        "alarm_id IS NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_emergencies_alarm_id ON emergencies (alarm_id)",
    ),
    (
        "repairs",
        "patrol_id",
        "patrol_id IS NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_repairs_patrol_id ON repairs (patrol_id)",
    ),
    (
        "plans",
        "area_id, fire_type",
        "area_id IS NOT NULL AND fire_type IS NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_plans_area_fire_type ON plans (area_id, fire_type) WHERE area_id IS NOT NULL",
    ),
]


def _table_columns(conn, table: str):
    return {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()}


def _apply_unique_indexes(conn, tables):
    """先剔除重复数据（保留最早一条），再创建唯一索引；表/列缺失时跳过。"""
    for table, key_cols, where, ddl in _UNIQUE_INDEX_RULES:
        if table not in tables:
            continue
        cols = _table_columns(conn, table)
        key_parts = [c.strip() for c in key_cols.split(",")]
        if not all(c in cols for c in key_parts):
            continue
        conn.execute(
            text(
                f"DELETE FROM {table} WHERE {where} AND id NOT IN "
                f"(SELECT MIN(id) FROM {table} WHERE {where} GROUP BY {key_cols})"
            )
        )
        conn.execute(text(ddl))


def run_migrations(engine):
    """对齐旧版本 fire_alarm.db：缺列则补列、去重并补唯一索引，不删库。全新库无需操作。"""
    with engine.connect() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            ).fetchall()
        }
        for table, cols in _MIGRATIONS.items():
            if table not in tables:
                continue
            existing = _table_columns(conn, table)
            for col, ddl in cols:
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
        _apply_unique_indexes(conn, tables)
        conn.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
