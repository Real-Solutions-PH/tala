"""Push the 6 seed document photos through ingestion (vision, Docling, embeddings) for Lola Remy.

Needs the model servers (./run.sh). Uses KAPILING_DATA like the app; seeds the persona first if the database is empty.
    uv run python -m seed.ingest_seed
"""

import asyncio
import sys
import time

from kapiling import db
from kapiling.docs.ingest import enqueue, process_one
from seed import persona

DOCS = [  # file, title, kind
    ("lab_fbs_hba1c.jpg", "FBS and HbA1c — 2026-03-02", "lab"),
    ("lab_lipid.jpg", f"Lipid profile — {persona.LIPID_DATE}", "lab"),
    ("lab_cbc.jpg", f"Complete blood count — {persona.CBC_DATE}", "lab"),
    ("lab_creatinine.jpg", f"Renal function test — {persona.CREATININE_DATE}", "lab"),
    ("discharge_2019.jpg", "Discharge summary — 2019-08-18", "discharge"),
    ("prescription.jpg", "Prescription — 2026-03-02", "prescription"),
]


async def main() -> int:
    con = db.connect()
    try:
        if not con.execute("select count(*) from profiles").fetchone()[0]:
            persona.seed(con)
        lola = con.execute("select id from profiles where nickname='Lola Remy'").fetchone()[0]
        failed = 0
        for name, title, kind in DOCS:
            did = enqueue(con, lola, (persona.ASSETS / name).read_bytes(), name, "image/jpeg", title, kind)
            status = con.execute("select status from documents where id=?", (did,)).fetchone()[0]
            if status != "indexed":
                t = time.monotonic()
                await process_one(con, did)
                row = con.execute("select status, error from documents where id=?", (did,)).fetchone()
                status = row["status"] + (f" ({row['error']})" if row["error"] else "")
                print(f"{name}: {status} in {time.monotonic() - t:.1f} s", flush=True)
            else:
                print(f"{name}: already indexed", flush=True)
            failed += status.startswith("failed")
        return 1 if failed else 0
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
