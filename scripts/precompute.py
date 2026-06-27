"""Build all deterministic caches before starting the demo.

Run from repository root:
    python scripts/precompute.py
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from compass.fva import build_fva_base, get_headline_stats, get_replay_chart_data
from compass.loader import DATA_ROOT, validate_dataset
from compass.store import DB_PATH, init_db, seed_hierarchy

OUTPUT_ROOT = PROJECT_ROOT / "data"


def main() -> None:
    print(f"Validating dataset at {DATA_ROOT} ...")
    manifest = validate_dataset()

    print(f"Initialising DuckDB at {DB_PATH} ...")
    init_db()

    print("Seeding valid forecast hierarchy ...")
    hierarchy_rows = seed_hierarchy()

    print("Building leakage-safe H+1 FVA base ...")
    fva = build_fva_base(OUTPUT_ROOT / "fva_base.parquet")

    print("Caching replay chart and headline statistics ...")
    chart = get_replay_chart_data()
    chart.to_parquet(OUTPUT_ROOT / "replay_chart_cache.parquet", index=False)
    stats = get_headline_stats()
    with (OUTPUT_ROOT / "headline_stats.json").open("w", encoding="utf-8") as handle:
        json.dump(stats, handle, indent=2)

    run_manifest = {
        "source_tables": len(manifest),
        "hierarchy_rows": hierarchy_rows,
        "fva_rows": len(fva),
        "fva_cutoffs": int(fva["cutoff_date"].nunique()),
        "outputs": [
            "data/compass.duckdb",
            "data/fva_base.parquet",
            "data/replay_chart_cache.parquet",
            "data/headline_stats.json",
        ],
    }
    with (OUTPUT_ROOT / "precompute_manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(run_manifest, handle, indent=2)

    if len(fva) < 50_000 or fva["cutoff_date"].nunique() < 20:
        raise RuntimeError("FVA join returned unexpectedly few rows; check grain alignment.")

    print(json.dumps(run_manifest, indent=2))
    print("Precompute complete.")


if __name__ == "__main__":
    main()
