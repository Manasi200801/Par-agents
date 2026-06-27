# scripts/precompute.py
# Run: python scripts/precompute.py
# Takes ~2 minutes. Caches results so the demo never hits raw parquet at runtime.
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from compass.fva import get_headline_stats, get_replay_chart_data
from compass.store import init_db, seed_hierarchy

print("Initialising database...")
init_db()

print("Seeding hierarchy...")
seed_hierarchy()

print("Caching replay chart data...")
chart = get_replay_chart_data()
chart.to_parquet("data/replay_chart_cache.parquet", index=False)

print("Caching headline stats...")
stats = get_headline_stats()
with open("data/headline_stats.json", "w") as f:
    json.dump(stats, f, indent=2, default=float)

print("Done. Run this before every demo.")
