# scripts/precompute.py
# Run: python scripts/precompute.py
# Takes ~30 seconds. Run once before the demo to init DB and cache FVA data.

import json
from compass.store import init_db, seed_hierarchy
from compass.fva   import get_replay_chart_data, get_headline_stats

print("Initialising database...")
init_db()

print("Seeding hierarchy...")
seed_hierarchy()

print("Caching replay chart data...")
chart = get_replay_chart_data()
chart.to_parquet("data/replay_chart_cache.parquet", index=False)
print(f"  {len(chart)} cutoff cycles cached.")

print("Caching headline stats...")
stats = get_headline_stats()
with open("data/headline_stats.json", "w") as f:
    json.dump(stats, f, indent=2)
print(f"  MAE machine: {stats['mae_machine']:.1f}, MAE planner: {stats['mae_planner']:.1f}")
print(f"  Upward overrides help: {stats['upward_pct_helped']:.0%}")
print(f"  Downward overrides help: {stats['downward_pct_helped']:.0%}")

print()
print("Done. Run this before every demo.")
