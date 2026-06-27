# scripts/inject_events.py
# Run: python scripts/inject_events.py
# Must be run AFTER scripts/precompute.py (DB must be initialised)

from compass.memory import seed_demo_events
import datetime

EVENTS = [
    # ── Competitor exit events (upward, usually right) ────────────────────────
    {
        "decision_id":    "demo-event-001",
        "cutoff_date":    datetime.date(2025, 3, 1),
        "product_id":     "CP-0271",
        "sales_org_id":   "SO04",
        "channel_id":     "CH01",
        "decision_maker": "planner_anna",
        "reason_text":    "Competitor Bauer Tools rumoured to be exiting DACH market for bearings",
        "reason_class":   "competitor_exit",
        "machine_value":  437.0,
        "override_value": 524.0,
        "final_value":    524.0,
        "outcome":        511.0,
        "fva":            74.0,
    },
    {
        "decision_id":    "demo-event-002",
        "cutoff_date":    datetime.date(2025, 4, 1),
        "product_id":     "PC-0084",
        "sales_org_id":   "SO02",
        "channel_id":     "CH01",
        "decision_maker": "planner_anna",
        "reason_text":    "Heard from trade show that rival exiting Nordic fasteners segment",
        "reason_class":   "competitor_exit",
        "machine_value":  310.0,
        "override_value": 372.0,
        "final_value":    372.0,
        "outcome":        348.0,
        "fva":            38.0,
    },
    {
        "decision_id":    "demo-event-003",
        "cutoff_date":    datetime.date(2025, 5, 1),
        "product_id":     "SM-0507",
        "sales_org_id":   "SO08",
        "channel_id":     "CH02",
        "decision_maker": "planner_marco",
        "reason_text":    "Key competitor pulling out of composites in France",
        "reason_class":   "competitor_exit",
        "machine_value":  195.0,
        "override_value": 234.0,
        "final_value":    234.0,
        "outcome":        228.0,
        "fva":            30.0,
    },
    # ── Channel overstock events (downward, often wrong) ─────────────────────
    {
        "decision_id":    "demo-event-004",
        "cutoff_date":    datetime.date(2025, 2, 1),
        "product_id":     "CP-0271",
        "sales_org_id":   "SO04",
        "channel_id":     "CH01",
        "decision_maker": "planner_marco",
        "reason_text":    "Customer says they are overstocked, will skip one order",
        "reason_class":   "channel_overstock",
        "machine_value":  420.0,
        "override_value": 294.0,
        "final_value":    294.0,
        "outcome":        398.0,
        "fva":            -82.0,
    },
    {
        "decision_id":    "demo-event-005",
        "cutoff_date":    datetime.date(2025, 1, 1),
        "product_id":     "PC-0029",
        "sales_org_id":   "SO01",
        "channel_id":     "CH01",
        "decision_maker": "planner_anna",
        "reason_text":    "Distributor mentioned high stock levels in Q4",
        "reason_class":   "channel_overstock",
        "machine_value":  610.0,
        "override_value": 427.0,
        "final_value":    427.0,
        "outcome":        578.0,
        "fva":            -119.0,
    },
    # ── Promotion events (upward, usually helps) ──────────────────────────────
    {
        "decision_id":    "demo-event-006",
        "cutoff_date":    datetime.date(2025, 6, 1),
        "product_id":     "CP-0271",
        "sales_org_id":   "SO04",
        "channel_id":     "CH02",
        "decision_maker": "planner_anna",
        "reason_text":    "Amazon promotion running for the whole category next month",
        "reason_class":   "promotion",
        "machine_value":  250.0,
        "override_value": 312.0,
        "final_value":    312.0,
        "outcome":        305.0,
        "fva":            48.0,
    },
    {
        "decision_id":    "demo-event-007",
        "cutoff_date":    datetime.date(2025, 7, 1),
        "product_id":     "SM-0507",
        "sales_org_id":   "SO08",
        "channel_id":     "CH02",
        "decision_maker": "planner_marco",
        "reason_text":    "Black Friday campaign confirmed for Consumer Products in France",
        "reason_class":   "promotion",
        "machine_value":  180.0,
        "override_value": 225.0,
        "final_value":    225.0,
        "outcome":        218.0,
        "fva":            31.0,
    },
    # ── Supply constraint events (varied) ─────────────────────────────────────
    {
        "decision_id":    "demo-event-008",
        "cutoff_date":    datetime.date(2025, 3, 1),
        "product_id":     "PC-0084",
        "sales_org_id":   "SO01",
        "channel_id":     "CH01",
        "decision_maker": "planner_marco",
        "reason_text":    "Main supplier confirmed delay due to port congestion in Shanghai",
        "reason_class":   "supply_constraint",
        "machine_value":  380.0,
        "override_value": 285.0,
        "final_value":    285.0,
        "outcome":        271.0,
        "fva":            95.0,
    },
    # ── Macro signal events ────────────────────────────────────────────────────
    {
        "decision_id":    "demo-event-009",
        "cutoff_date":    datetime.date(2025, 4, 1),
        "product_id":     "SM-0507",
        "sales_org_id":   "SO04",
        "channel_id":     "CH01",
        "decision_maker": "planner_anna",
        "reason_text":    "New EU tariff on Southeast Asia materials announced, will raise costs",
        "reason_class":   "macro_signal",
        "machine_value":  220.0,
        "override_value": 198.0,
        "final_value":    198.0,
        "outcome":        215.0,
        "fva":            -17.0,
    },
    # ── Price change events ────────────────────────────────────────────────────
    {
        "decision_id":    "demo-event-010",
        "cutoff_date":    datetime.date(2025, 5, 1),
        "product_id":     "CP-0271",
        "sales_org_id":   "SO02",
        "channel_id":     "CH01",
        "decision_maker": "planner_marco",
        "reason_text":    "We are raising list price by 8% next month — expect some demand drop",
        "reason_class":   "price_change",
        "machine_value":  390.0,
        "override_value": 351.0,
        "final_value":    351.0,
        "outcome":        362.0,
        "fva":            -11.0,
    },
]

if __name__ == "__main__":
    print(f"Injecting {len(EVENTS)} demo events...")
    seed_demo_events(EVENTS)
    print("Done. Memory layer now has scored history for the demo.")
    print()
    print("Track record summary:")
    from collections import defaultdict
    by_class = defaultdict(list)
    for e in EVENTS:
        by_class[e['reason_class']].append(e['fva'])
    for cls, fvas in by_class.items():
        avg = sum(fvas) / len(fvas)
        print(f"  {cls}: n={len(fvas)}, avg_fva={avg:+.1f}")
