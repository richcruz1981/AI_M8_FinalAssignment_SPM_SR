// PepsiCo-inspired palette (corporate logo colors per Coloropedia; series steps validated with the
// dataviz validator: lightness band, CVD separation and normal-vision floor all PASS).
export const UI = {
  navy: "#28458E", // PepsiCo dark cornflower blue — header / primary text accents
  electric: "#0096D6", // PepsiCo rich electric blue — accents, focus
  page: "#F4F6FA",
  card: "#FFFFFF",
  ink: "#14213D",
  ink2: "#5B6475",
  grid: "#E6EAF1",
  border: "#E1E6EE",
};
// Categorical series, fixed order (never cycled): brand blue step, PepsiCo tangelo, PepsiCo electric blue.
export const SERIES = ["#3D63C4", "#EB7B30", "#0096D6"];
// Health status — reserved, always paired with a text label. Green/red are PepsiCo brand greens/reds.
export const STATUS = { Green: "#00984A", Amber: "#E0A000", Red: "#DF002C", "No data": "#A7AEBB" };
export const STATUS_ORDER = ["Green", "Amber", "Red", "No data"];
export const SEVERITY = { High: "#DF002C", Medium: "#EB7B30", Low: "#E0A000" };
export const CMP = { Consistent: "#3D63C4", Optimistic: "#EB7B30", Conservative: "#0096D6", "Not comparable": "#A7AEBB" };
export const KPI_HEALTH = [
  ["overall", "1 · Overall"],
  ["schedule", "2 · Schedule"],
  ["cost", "3 · Cost"],
  ["resources", "4 · Resources"],
  ["scope", "5 · Scope"],
];
