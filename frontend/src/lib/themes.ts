export type ThemeOption = {
  id: string;
  label: string;
  description: string;
  preview: {
    from: string;
    to: string;
    accent: string;
  };
  group: "custom" | "system";
};

export const customThemes: ThemeOption[] = [
  {
    id: "obsidian",
    label: "Obsidian",
    description: "Deep monochrome black.",
    preview: { from: "oklch(0.08 0 0)", to: "oklch(0.12 0 0)", accent: "oklch(0.98 0 0)" },
    group: "custom",
  },
  {
    id: "sunburst",
    label: "Sunburst",
    description: "Bright, optimistic warmth with golden accents.",
    preview: { from: "oklch(0.97 0.02 85)", to: "oklch(0.92 0.06 75)", accent: "oklch(0.72 0.18 55)" },
    group: "custom",
  },
  {
    id: "oceanic",
    label: "Oceanic",
    description: "Deep indigo and violet depth.",
    preview: { from: "oklch(0.64 0.24 265)", to: "oklch(0.7 0.2 280)", accent: "oklch(0.7 0.22 280)" },
    group: "custom",
  },
  {
    id: "berry",
    label: "Berry",
    description: "Vibrant pink and fuchsia tones.",
    preview: { from: "oklch(0.65 0.28 340)", to: "oklch(0.75 0.25 320)", accent: "oklch(0.7 0.24 300)" },
    group: "custom",
  },
  {
    id: "citrus",
    label: "Citrus",
    description: "Dark amber warmth with energetic orange accents.",
    preview: { from: "oklch(0.18 0.04 55)", to: "oklch(0.24 0.06 50)", accent: "oklch(0.72 0.2 55)" },
    group: "custom",
  },
  {
    id: "ember",
    label: "Ember",
    description: "Warm reds with amber glow.",
    preview: { from: "oklch(0.7 0.24 35)", to: "oklch(0.8 0.2 75)", accent: "oklch(0.6 0.25 25)" },
    group: "custom",
  },
  {
    id: "graphite",
    label: "Graphite",
    description: "Dark slate with electric teal.",
    preview: { from: "oklch(0.32 0.05 220)", to: "oklch(0.62 0.2 205)", accent: "oklch(0.7 0.2 175)" },
    group: "custom",
  },
  {
    id: "studioMidnight",
    label: "Studio Midnight",
    description: "Calm navy depth for focused work sessions.",
    preview: { from: "oklch(0.14 0.03 255)", to: "oklch(0.2 0.04 250)", accent: "oklch(0.68 0.16 210)" },
    group: "custom",
  },
  {
    id: "editorialSlate",
    label: "Editorial Slate",
    description: "Bold, warm slate with striking amber accent.",
    preview: { from: "oklch(0.95 0.01 250)", to: "oklch(0.88 0.02 245)", accent: "oklch(0.74 0.18 65)" },
    group: "custom",
  },
];

export const systemThemes: ThemeOption[] = [
  {
    id: "light",
    label: "Light",
    description: "Default light theme.",
    preview: { from: "oklch(0.98 0.01 210)", to: "oklch(0.88 0.05 215)", accent: "oklch(0.68 0.24 205)" },
    group: "system",
  },
  {
    id: "dark",
    label: "Dark",
    description: "Standard dark theme.",
    preview: { from: "oklch(0.18 0.008 240)", to: "oklch(0.22 0.008 240)", accent: "oklch(0.9 0.02 240)" },
    group: "system",
  },
  {
    id: "system",
    label: "System",
    description: "Match your OS preference.",
    preview: { from: "oklch(0.9 0.02 210)", to: "oklch(0.7 0.1 210)", accent: "oklch(0.6 0.18 205)" },
    group: "system",
  },
];

export const allThemeIds = [
  ...customThemes.map((theme) => theme.id),
  ...systemThemes.map((theme) => theme.id),
];