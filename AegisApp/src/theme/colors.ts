// IntelliPlant premium theme — dark industrial control-room aesthetic.
// A single source of truth for color, spacing, radius and typography so every
// screen looks like the same product instead of a pile of ad-hoc styles.

export const colors = {
  bg: '#0b0f17',
  bgElevated: '#0f1420',
  surface: '#131926',
  surface2: '#182032',
  surface3: '#1f2940',
  border: '#232c40',
  borderLight: '#2b3650',

  textPrimary: '#eef2f8',
  textSecondary: '#a7b3c8',
  textFaint: '#6b7793',

  accent: '#4fa3ff',
  accentSoft: 'rgba(79,163,255,0.14)',
  accentDeep: '#1f6feb',

  green: '#3ecf8e',
  greenSoft: 'rgba(62,207,142,0.14)',
  amber: '#f5a623',
  amberSoft: 'rgba(245,166,35,0.14)',
  red: '#f0575d',
  redSoft: 'rgba(240,87,93,0.14)',
  blue: '#4fa3ff',
  blueSoft: 'rgba(79,163,255,0.14)',
  gray: '#8a94a8',
  graySoft: 'rgba(138,148,168,0.14)',

  white: '#ffffff',
  black: '#000000',
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
};

export const radius = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 22,
  pill: 999,
};

export const typography = {
  h1: { fontSize: 26, fontWeight: '700' as const, letterSpacing: -0.3 },
  h2: { fontSize: 20, fontWeight: '700' as const, letterSpacing: -0.2 },
  h3: { fontSize: 16, fontWeight: '600' as const },
  body: { fontSize: 14, fontWeight: '400' as const },
  small: { fontSize: 12.5, fontWeight: '400' as const },
  mono: { fontFamily: 'Menlo', fontSize: 12.5 },
};

export type Tone = 'green' | 'amber' | 'red' | 'blue' | 'gray';

export function toneColor(tone: Tone) {
  switch (tone) {
    case 'green':
      return colors.green;
    case 'amber':
      return colors.amber;
    case 'red':
      return colors.red;
    case 'blue':
      return colors.blue;
    default:
      return colors.gray;
  }
}

export function toneSoft(tone: Tone) {
  switch (tone) {
    case 'green':
      return colors.greenSoft;
    case 'amber':
      return colors.amberSoft;
    case 'red':
      return colors.redSoft;
    case 'blue':
      return colors.blueSoft;
    default:
      return colors.graySoft;
  }
}
