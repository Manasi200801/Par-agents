# Arve Holding AG — Sample Datasets

Synthetic sample data (fictional companies, **no real customers and no PII**) for
forecasting and analytics experimentation. Three independent, self-contained
datasets. All monetary values are in EUR.

## Datasets

| Folder | Company | Contents |
|---|---|---|
| `alpine-manufacturing-gmbh/` | Alpine Manufacturing GmbH (Stuttgart industrial group) | Source business tables + demand forecast |
| `alpine-manufacturing-forecast/` | Alpine Manufacturing (item-level variant) | Source business tables + demand forecast + naive baseline |
| `firn-outdoor-ag/` | Firn Outdoor AG (Zurich DTC outdoor-apparel brand) | Source business tables only (no forecast) |

## Folder convention (inside each dataset)

| Subfolder | Meaning |
|---|---|
| `source-data/` | Cleaned source business tables (sales, stock, products, customers, suppliers, plans, …) |
| `forecast-input/` | The prepared modelling series fed to the forecast |
| `forecast-output/` | Forecast results: forward forecast, rolling backtest, error metrics, item master |
| `forecast-baseline/` | Naive baseline forecast for comparison (Alpine forecast variant only) |

Each dataset folder has its own `README.md` with a per-file data dictionary.

## Notes

- **Coherence.** Within a dataset, the forecast input and output come from the same
  forecast run. Source extracts and forecast runs may differ in date (data is a
  point-in-time sample, not a live feed).
- **Deduplication.** Where a forecast's input table is fully contained in its output,
  only the (richer) output copy is kept; derived modelling tables (`meta_data`,
  `target_time_series`) were removed from `source-data/` since they live in the
  forecast folders.
- **Shared master data.** The two Alpine datasets share much of their reference data
  (identical product, customer, supplier, channel and sales-org tables). Each folder
  keeps its own copy so it can be used standalone — expect overlap if you load both.
