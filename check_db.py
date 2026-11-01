
import sqlite3
from pathlib import Path

db = Path(__file__).resolve().parent / "attendance.db"
conn = sqlite3.connect(db)

for table in ("attendance", "students"):
    print(f"\n{table.upper()} INDEXES:")

    indexes = conn.execute(
        f'PRAGMA index_list("{table}")'
    ).fetchall()

    for index in indexes:
        name = index[1]
        columns = conn.execute(
            f'PRAGMA index_info("{name}")'
        ).fetchall()

        print(
            f"Unique: {bool(index[2])} | "
            f"Columns: {[col[2] for col in columns]}"
        )

conn.close()
