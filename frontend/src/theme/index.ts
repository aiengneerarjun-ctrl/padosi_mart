// Padosi design tokens: mohalle ki dukaan jaisa garam, par saaf-suthra.
export const colors = {
  ink: "#0E3B36",        // gehra hara: brand, headers
  inkSoft: "#1D5C54",
  marigold: "#F2A900",   // genda phool: main action
  marigoldDeep: "#C98A00",
  canvas: "#F4F7F6",     // screen background
  surface: "#FFFFFF",
  text: "#13211F",
  textMuted: "#5B6D6A",
  line: "#DDE5E3",
  success: "#1F8A4C",
  danger: "#C8372D",
  onInk: "#FFFFFF",
  onMarigold: "#2A1D00",
} as const;

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 } as const;

export const radius = { sm: 8, md: 14, lg: 22, pill: 999 } as const;

// Hind font Latin + Devanagari dono dikhata hai (en / hi / bho teeno bhasha).
export const font = {
  regular: "Hind_400Regular",
  medium: "Hind_500Medium",
  semibold: "Hind_600SemiBold",
  bold: "Hind_700Bold",
} as const;

export const type = {
  display: { fontFamily: font.bold, fontSize: 30, lineHeight: 36 },
  title: { fontFamily: font.semibold, fontSize: 22, lineHeight: 28 },
  heading: { fontFamily: font.semibold, fontSize: 17, lineHeight: 24 },
  body: { fontFamily: font.regular, fontSize: 15, lineHeight: 22 },
  caption: { fontFamily: font.regular, fontSize: 13, lineHeight: 18 },
} as const;

export const shadow = {
  // Sirf upar uthe hue elements par (sheet, floating cart bar). Har card par nahi.
  raised: {
    shadowColor: "#0E3B36",
    shadowOpacity: 0.14,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 8 },
    elevation: 6,
  },
} as const;
