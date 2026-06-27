Alpine Manufacturing GmbH is a fictional Stuttgart-based mid-cap industrial group organised into three business units — Precision Components, Consumer Products, and Specialty Materials — selling through B2B, Amazon, B2C, and Distributor channels across European sales organisations. This dataset bundles cleaned source business tables with a product × sales-org × channel demand forecast; all monetary values are in EUR.

## source-data/

| file | description | key columns |
|------|-------------|-------------|
| `alpine_products.parquet` | Product master — one row per SKU; BU → Category → Product Group hierarchy, lifecycle status, ABC class, pricing, and UoM conversions. | `product_id`, `business_unit`, `category`, `product_group`, `status`, `abc_class`, `list_price_eur`, `unit_cost_eur`, `base_uom` |
| `alpine_sales_actuals.parquet` | Daily sell-out fact at product × sales org × channel grain; zero-quantity rows indicate days without sales. | `product_id`, `sales_org_id`, `channel_id`, `date`, `quantity_bu`, `revenue_eur` |
| `alpine_sales_org.parquet` | Sales organisation master with country, region group (DACH, BeNeLux, Western EU, …), and associated warehouse per org. | `sales_org_id`, `sales_org_name`, `country`, `region_group`, `loc_id`, `loc_name` |
| `alpine_channels.parquet` | Channel lookup — CH01 = B2B, CH02 = Amazon, CH03 = B2C, CH04 = Distributor. | `channel_id`, `channel_name` |
| `alpine_customers.parquet` | Customer master with assigned sales org, primary channel, segment, and key-account flag. | `customer_id`, `customer_name`, `sales_org_id`, `channel_id`, `segment`, `key_account_flag` |
| `alpine_suppliers.parquet` | Supplier master with sourcing region, material category, and average lead time in weeks. | `supplier_id`, `supplier_name`, `sourcing_region`, `material_category`, `avg_lead_time_weeks` |
| `alpine_stock_on_hand.parquet` | Weekly stock-on-hand readings at product × sales org grain; quantity in product base UOM and value at unit cost. | `product_id`, `sales_org_id`, `date`, `stock_qty_bu`, `stock_value_eur` |
| `alpine_future_order_book.parquet` | Forward customer order lines (confirmed or tentative) at product × customer × sales org grain. | `product_id`, `customer_id`, `sales_org_id`, `order_date`, `requested_delivery_week`, `status`, `confirmed_qty` |
| `alpine_production_data.parquet` | Monthly planned vs actual production output at production line × product grain. | `line_id`, `product_id`, `period_month`, `planned_output`, `actual_output`, `capacity_units` |
| `alpine_marketing_spends.parquet` | Monthly campaign spend at category × sales org × channel grain; one row per campaign. | `campaign_id`, `category`, `sales_org_id`, `channel_id`, `period_month`, `campaign_type`, `spend_eur` |
| `alpine_demand_plan.parquet` | Weekly planner-adjusted demand plan at product × sales org grain; rolling monthly cutoff — filter `cutoff_date` to one vintage before aggregating. | `cutoff_date`, `product_id`, `sales_org_id`, `date`, `total_forecast_qty_bu` |
| `alpine_statistical_forecast.parquet` | Monthly machine-generated forecast at product × sales org grain; rolling cutoff — filter `cutoff_date` before aggregating. | `cutoff_date`, `product_id`, `sales_org_id`, `forecast_month`, `stat_forecast_qty_bu` |
| `alpine_business_plan.parquet` | Monthly revenue / margin plan at BU × category × sales org × channel grain; quarterly rolling cutoff. | `cutoff_date`, `business_unit`, `category`, `sales_org_id`, `channel_id`, `period_month`, `planned_revenue_eur`, `planned_gross_margin_eur` |
| `alpine_actuals_plan_forecast_monthly.parquet` | Long-format mart unifying actuals, plan, statistical forecast, and demand plan at BU × category × sales org × month; `series` discriminates the type. | `series`, `cutoff_date`, `business_unit`, `category`, `sales_org_id`, `period_month`, `qty_bu`, `revenue_eur` |
| `alpine_price_changes.parquet` | Effective list price history at product × sales org × channel grain; each row valid from `effective_month` onward. | `product_id`, `sales_org_id`, `channel_id`, `effective_month`, `price_eur_per_pcs` |
| `alpine_purchase_orders.parquet` | Supplier purchase order lines; ordered vs delivered quantity and expected vs actual delivery dates for OTIF analysis. | `po_id`, `supplier_id`, `product_id`, `order_date`, `expected_delivery_week`, `actual_delivery_week`, `ordered_qty`, `delivered_qty`, `po_value_eur` |
| `alpine_delivery_data.parquet` | Outbound customer delivery lines at product × customer × sales org grain. | `product_id`, `customer_id`, `sales_org_id`, `date`, `delivered_qty`, `revenue_eur` |
| `alpine_returns.parquet` | Customer return events with categorical reason codes; quantity in product base UOM and value in EUR. | `product_id`, `customer_id`, `sales_org_id`, `date`, `return_reason`, `return_qty`, `return_value_eur` |
| `alpine_cost_breakdown.parquet` | Monthly cost decomposition at BU × category grain: raw material, logistics, labour, and tariff surcharge. | `business_unit`, `category`, `period_month`, `raw_material_cost_eur`, `logistics_cost_eur`, `labor_cost_eur`, `tariff_surcharge_eur` |
| `alpine_tariff_reference.parquet` | Quarterly tariff rate reference by sourcing region × product category; use the latest `effective_date` for current rates. | `sourcing_region`, `product_category`, `effective_date`, `tariff_rate_pct` |

## forecast-input/

| file | description | key columns |
|------|-------------|-------------|
| `target_time_series.parquet` | Prepared modelling target series fed to the demand forecast; one row per forecast entity × date. | `item_id`, `date`, `target`, `exposure` |

## forecast-output/

| file | description | key columns |
|------|-------------|-------------|
| `live_forecasts.parquet` | Forward demand forecast per forecast entity and date. | `item_id`, `date`, `prediction` |
| `final_backtest_forecasts.parquet` | Rolling-origin backtest results; actual vs predicted per model, cutoff, and date. | `model`, `cutoff`, `item_id`, `date`, `target`, `prediction`, `exposure` |
| `final_error_metrics.parquet` | Per-item forecast error metrics. | `item_id`, `metric_FPE`, `metric_MAE`, `metric_MARRE`, `metric_RMSE` |
| `final_overall_error_metrics.parquet` | Dataset-level error metrics aggregated across all items (single row). | `metric_FPE`, `metric_MAE`, `metric_MARRE`, `metric_RMSE` |
| `meta_data.parquet` | Item master mapping each forecast entity (`item_id`) to its product, sales org, and channel attributes. | `item_id`, `item_name`, `product_id`, `sales_org_id`, `channel_id`, `product_name`, `business_unit`, `category`, `abc_class`, `unit_cost_eur`, `list_price_eur` |
