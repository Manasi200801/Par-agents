// Demo catalog data. Mirrors what P1's load_products() / load_sales_org() will
// eventually return. Hand-curated so the frontend runs fully offline before the
// backend is reachable. CP-0271 is the canonical demo SKU (real data everywhere).

export interface Product {
  product_id: string;
  name: string;
  business_unit: string;
  category: string;
  abc_class: "A" | "B" | "C";
  machine_value: number; // stat forecast for the demo cutoff
}

export interface SalesOrg {
  sales_org_id: string;
  name: string;
  region_group: string;
}

export const PRODUCTS: Product[] = [
  { product_id: "CP-0271", name: "Precision Bearing 6204-ZZ", business_unit: "Consumer Products", category: "Bearings & Bushings", abc_class: "A", machine_value: 437 },
  { product_id: "PC-0029", name: "Hex Flange Bolt M10", business_unit: "Process Components", category: "Fasteners", abc_class: "A", machine_value: 610 },
  { product_id: "PC-0084", name: "Threaded Rod 304-SS", business_unit: "Process Components", category: "Fasteners", abc_class: "B", machine_value: 310 },
  { product_id: "SM-0507", name: "Carbon Composite Panel", business_unit: "Specialty Materials", category: "Composites", abc_class: "A", machine_value: 280 },
];

export const SALES_ORGS: SalesOrg[] = [
  { sales_org_id: "SO01", name: "Central Distribution", region_group: "DACH" },
  { sales_org_id: "SO02", name: "Nordic Wholesale", region_group: "Nordics" },
  { sales_org_id: "SO04", name: "DACH Direct", region_group: "DACH" },
  { sales_org_id: "SO08", name: "Western Europe", region_group: "France & Benelux" },
];

export const CHANNELS = ["CH01", "CH02", "CH03", "CH04"] as const;

export const CHANNEL_LABELS: Record<string, string> = {
  CH01: "Distributor",
  CH02: "E-commerce",
  CH03: "Direct / Key Account",
  CH04: "Retail",
};

// The default demo selection — verified to have real data in every table.
export const DEMO_DEFAULT = {
  product_id: "CP-0271",
  sales_org_id: "SO04",
  channel_id: "CH01",
} as const;

export function productById(id: string): Product {
  return PRODUCTS.find((p) => p.product_id === id) ?? PRODUCTS[0];
}

export function orgById(id: string): SalesOrg {
  return SALES_ORGS.find((o) => o.sales_org_id === id) ?? SALES_ORGS[0];
}
