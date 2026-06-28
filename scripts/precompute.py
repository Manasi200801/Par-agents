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
print(f"  WAPE machine: {stats['wape_machine']:.1%}, WAPE planner: {stats['wape_planner']:.1%}")
print(f"  Planners helped (all):         {stats['pct_helped_all']:.0%}")
print(f"  Planners helped (meaningful):  {stats['pct_helped_meaningful']:.0%}")

print()
print("Done. Run this before every demo.")
