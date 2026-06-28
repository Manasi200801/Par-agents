"""
Seed realistic historical decisions into compass.duckdb for demo purposes.
Run once: python scripts/seed_demo_data.py
Safe to re-run — clears existing demo rows before inserting.
"""
import sys, os, uuid
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from compass.store import get_conn

# ── helpers ──────────────────────────────────────────────────────────────────

def fva_row(machine, override, actual, reason_class, reason_text, planner,
            cutoff, target, reconciler_value=None, final=None):
    if final is None:
        final = override
    if reconciler_value is None:
        reconciler_value = round((machine + override) / 2, 1)
    machine_error   = abs(actual - machine)
    override_error  = abs(actual - override)
    reconciler_error= abs(actual - reconciler_value)
    final_error     = abs(actual - final)
    fva             = machine_error - final_error
    compass_va      = machine_error - reconciler_error
    return dict(
        decision_id      = str(uuid.uuid4()),
        cutoff_date      = cutoff,
        target_month     = target,
        item_id          = None,
        machine_value    = float(machine),
        override_value   = float(override),
        reconciler_value = float(reconciler_value),
        final_value      = float(final),
        reason_text      = reason_text,
        reason_class     = reason_class,
        decision_maker   = planner,
        context_json     = "{}",
        outcome          = float(actual),
        machine_error    = float(machine_error),
        proposed_error   = float(override_error),
        reconciler_error = float(reconciler_error),
        override_error   = float(override_error),
        fva              = float(fva),
        compass_value_added = float(compass_va),
        scored_at        = datetime(2026, 6, 1, 8, 0, 0),
    )


# ── seed rows ────────────────────────────────────────────────────────────────

ROWS = [
    # ── planner_001 ──────────────────────────────────────────────────────────
    # competitor_exit × 3 (all helped)
    fva_row(800, 1040, 970,
            "competitor_exit",
            "Main competitor announced exit from DACH market — expecting demand to shift to us in Q2.",
            "planner_001", date(2026,1,1), date(2026,2,1), reconciler_value=960, final=1040),

    fva_row(750, 950, 880,
            "competitor_exit",
            "Heard from sales rep that Müller GmbH is winding down their bearing product line.",
            "planner_001", date(2025,11,1), date(2025,12,1), reconciler_value=900, final=950),

    fva_row(900, 1110, 1020,
            "competitor_exit",
            "Competitor exiting Nordics per trade press. Expected uplift of 10-15% across DACH channels.",
            "planner_001", date(2025,8,1), date(2025,9,1), reconciler_value=1020, final=1110),

    # promotion × 1 (helped)
    fva_row(1900, 2280, 2150,
            "promotion",
            "Trade show campaign running in SO16 for Bearings category — historically drives +20% volume.",
            "planner_001", date(2025,10,1), date(2025,11,1), reconciler_value=2150, final=2280),

    # customer_request × 2 (one helped, one hurt)
    fva_row(2700, 3300, 3200,
            "customer_request",
            "Bosch confirmed a large order uplift for next quarter — want to cover their requested volume.",
            "planner_001", date(2025,9,1), date(2025,10,1), reconciler_value=3100, final=3300),

    fva_row(2600, 3000, 2750,
            "customer_request",
            "Key account requested we pre-position extra stock ahead of their annual shutdown.",
            "planner_001", date(2025,6,1), date(2025,7,1), reconciler_value=2800, final=3000),

    # weather_event × 1 (helped)
    fva_row(2300, 1900, 2050,
            "weather_event",
            "Severe winter forecast for Nordics — expect logistics delays and demand softness in Jan.",
            "planner_001", date(2024,12,1), date(2025,1,1), reconciler_value=2000, final=1900),

    # supply_constraint × 1 (hurt — machine was almost right, planner over-corrected downward)
    fva_row(4200, 3800, 4100,
            "supply_constraint",
            "Supplier OTIF has been low, worried we can't deliver the machine number. Reducing commit.",
            "planner_001", date(2025,5,1), date(2025,6,1), reconciler_value=4000, final=3800),

    # ── Anna M. ──────────────────────────────────────────────────────────────
    # promotion × 2 (both helped)
    fva_row(4000, 4800, 4600,
            "promotion",
            "Digital campaign for Measuring Instruments in SO03 runs for 6 weeks — should lift demand 15-20%.",
            "Anna M.", date(2026,2,1), date(2026,3,1), reconciler_value=4500, final=4800),

    fva_row(3500, 4200, 3900,
            "promotion",
            "Social media push for calipers in DACH — sales team expects meaningful uplift.",
            "Anna M.", date(2025,7,1), date(2025,8,1), reconciler_value=3900, final=4200),

    # competitor_exit × 1 (helped)
    fva_row(2700, 3300, 3100,
            "competitor_exit",
            "Competitor Tesa reducing product catalogue per their annual report — DACH opportunity.",
            "Anna M.", date(2025,10,1), date(2025,11,1), reconciler_value=3000, final=3300),

    # supply_constraint × 1 (helped)
    fva_row(2800, 2400, 2600,
            "supply_constraint",
            "SO04 supplier running at 78% OTIF last two months. Reducing to avoid over-promising.",
            "Anna M.", date(2025,12,1), date(2026,1,1), reconciler_value=2550, final=2400),

    # weather_event × 1 (hurt — planner cut too much)
    fva_row(4700, 3900, 4300,
            "weather_event",
            "Heat wave forecast for Southern EU — outdoor tool demand typically dips.",
            "Anna M.", date(2025,6,1), date(2025,7,1), reconciler_value=4200, final=3900),

    # ── Lars B. ──────────────────────────────────────────────────────────────
    # competitor_exit × 1 (hurt — override overshoot)
    fva_row(1900, 2300, 2050,
            "competitor_exit",
            "Rumour that UK-based competitor is cutting back — may shift some volume our way.",
            "Lars B.", date(2025,9,1), date(2025,10,1), reconciler_value=2100, final=2300),

    # promotion × 1 (helped)
    fva_row(4000, 4700, 4500,
            "promotion",
            "Major trade event in BeNeLux for Power Tools — sponsorship secured, expect strong pull-through.",
            "Lars B.", date(2025,11,1), date(2025,12,1), reconciler_value=4400, final=4700),

    # customer_request × 1 (helped)
    fva_row(2500, 2900, 2700,
            "customer_request",
            "Siemens UK requested additional allocation for their maintenance programme renewal.",
            "Lars B.", date(2026,1,1), date(2026,2,1), reconciler_value=2750, final=2900),

    # weather_event × 1 (hurt — machine was closer than planner)
    fva_row(5000, 4200, 4500,
            "weather_event",
            "Cold snap in Southern EU expected to reduce construction activity and tool demand.",
            "Lars B.", date(2025,8,1), date(2025,9,1), reconciler_value=4600, final=4200),

    # supply_constraint × 1 (hurt)
    fva_row(5000, 4400, 4700,
            "supply_constraint",
            "Production attainment has been 82% — reducing forecast to stay conservative.",
            "Lars B.", date(2025,5,1), date(2025,6,1), reconciler_value=4700, final=4400),
]


# ── write to DB ──────────────────────────────────────────────────────────────

COLS = [
    "decision_id","cutoff_date","target_month","item_id","machine_value",
    "override_value","reconciler_value","final_value","reason_text","reason_class",
    "decision_maker","context_json","outcome","machine_error","proposed_error",
    "reconciler_error","override_error","fva","compass_value_added","scored_at",
]

with get_conn() as conn:
    # Clear existing demo data (decisions with no item_id = seeded)
    deleted = conn.execute(
        "DELETE FROM decisions WHERE item_id IS NULL"
    ).rowcount
    if deleted:
        print(f"Cleared {deleted} previous demo rows.")

    placeholders = ", ".join(["?"] * len(COLS))
    sql = f"INSERT INTO decisions ({', '.join(COLS)}) VALUES ({placeholders})"

    for row in ROWS:
        conn.execute(sql, [row[c] for c in COLS])

    # Verify
    counts = conn.execute("""
        SELECT decision_maker, COUNT(*) AS n,
               ROUND(AVG(CASE WHEN fva > 0 THEN 1.0 ELSE 0.0 END)*100) AS pct_helpful,
               ROUND(AVG(fva)) AS avg_fva
        FROM decisions WHERE fva IS NOT NULL
        GROUP BY decision_maker ORDER BY decision_maker
    """).df()
    print(f"\nInserted {len(ROWS)} demo decisions.\n")
    print("Planner track records:")
    print(counts.to_string(index=False))

    reason_stats = conn.execute("""
        SELECT reason_class, COUNT(*) AS n,
               ROUND(AVG(fva)) AS avg_fva,
               ROUND(AVG(CASE WHEN fva > 0 THEN 1.0 ELSE 0.0 END)*100) AS pct_helpful,
               ROUND(AVG((override_value - machine_value) / machine_value)*100, 1) AS avg_override_pct,
               ROUND(AVG((outcome - machine_value) / machine_value)*100, 1) AS avg_realized_pct
        FROM decisions WHERE fva IS NOT NULL
        GROUP BY reason_class ORDER BY reason_class
    """).df()
    print("\nReason class track records:")
    print(reason_stats.to_string(index=False))

print("\nDone. Restart the Streamlit app for the cache to clear.")
