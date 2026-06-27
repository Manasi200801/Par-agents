// Helpers over the auto-generated real catalog (lib/catalog-data.ts).
// Keep the generated file untouched; add UI conveniences here.

export * from "./catalog-data";
import { PRODUCTS, SALES_ORGS, MACHINE_FORECAST } from "./catalog-data";

// Channels are not part of the statistical forecast (which is product × org ×
// month), so the channel selector is contextual only and does not change the
// machine number.
export const CHANNELS = ["CH01", "CH02", "CH03", "CH04"] as const;
export const CHANNEL_LABELS: Record<string, string> = {
  CH01: "Distributor",
  CH02: "E-commerce",
  CH03: "Direct / Key Account",
  CH04: "Retail",
};

export const DEMO_DEFAULT = {
  product_id: "CP-0271",
  channel_id: "CH01",
} as const;

export function productById(id: string) {
  return PRODUCTS.find((p) => p.product_id === id) ?? PRODUCTS[0];
}
export function orgById(id: string) {
  return SALES_ORGS.find((o) => o.sales_org_id === id) ?? SALES_ORGS[0];
}

/** Sales orgs that have a real forecast for this product. */
export function orgsForProduct(productId: string) {
  const m = MACHINE_FORECAST[productId] ?? {};
  return SALES_ORGS.filter((o) => m[o.sales_org_id] != null);
}

/** Real statistical (machine) forecast for a product × org, in units. */
export function machineFor(productId: string, orgId: string): number {
  return MACHINE_FORECAST[productId]?.[orgId] ?? 0;
}
