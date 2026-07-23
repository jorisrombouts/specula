export const SCOPE_TYPES = ["Any", "Region", "Country", "City"] as const;
export type ScopeType = (typeof SCOPE_TYPES)[number];

// Curated frontend catalogs (data-quality pickers; backend does not validate).
export const REGIONS: string[] = [
  "EU",
  "EEA",
  "Eurozone",
  "Nordics",
  "DACH",
  "Benelux",
  "UK & Ireland",
  "Southern Europe",
  "North America",
  "LATAM",
  "Global",
];
export const COUNTRIES: [string, string][] = [
  ["NL", "Netherlands"],
  ["DE", "Germany"],
  ["FR", "France"],
  ["ES", "Spain"],
  ["IT", "Italy"],
  ["PT", "Portugal"],
  ["BE", "Belgium"],
  ["IE", "Ireland"],
  ["DK", "Denmark"],
  ["SE", "Sweden"],
  ["NO", "Norway"],
  ["FI", "Finland"],
  ["PL", "Poland"],
  ["AT", "Austria"],
  ["CH", "Switzerland"],
  ["CZ", "Czechia"],
  ["GB", "United Kingdom"],
  ["US", "United States"],
  ["CA", "Canada"],
];

export const ORIGIN_OPTIONS: { label: string; value: string }[] = [
  { label: "Any HQ", value: "" },
  { label: "Only foreign HQ", value: "foreign_hq" },
  { label: "Only domestic HQ", value: "domestic_hq" },
];
export const originLabel = (value: string): string =>
  ORIGIN_OPTIONS.find((o) => o.value === value)?.label ?? "Any HQ";

export type ScopeParts = { type: ScopeType; value: string };

// scope text (stored) -> structured. Region catalog is checked FIRST so a 2-letter
// region ("EU") isn't mistaken for a country code.
export function parseScope(text: string): ScopeParts {
  const t = (text ?? "").trim();
  if (t === "") return { type: "Any", value: "" };
  if (REGIONS.includes(t)) return { type: "Region", value: t };
  if (/^[A-Z]{2}$/.test(t)) return { type: "Country", value: t };
  return { type: "City", value: t };
}
export function serializeScope({ type, value }: ScopeParts): string {
  return type === "Any" ? "" : value.trim();
}
