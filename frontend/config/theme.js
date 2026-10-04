const theme = {
  colors: {
    primary: '#004AC6',
    primaryContainer: '#2563EB',
    onPrimary: '#FFFFFF',
    onPrimaryContainer: '#EEEFFF',
    primaryFixed: '#DBE1FF',
    primaryFixedDim: '#B4C5FF',

    secondary: '#006E2D',
    secondaryContainer: '#7CF994',
    onSecondary: '#FFFFFF',
    onSecondaryContainer: '#007230',

    tertiary: '#0D46D1',
    tertiaryContainer: '#3761EA',

    surface: '#FAF8FF',
    surfaceContainer: '#EAEDFF',
    surfaceContainerLow: '#F2F3FF',
    surfaceContainerHigh: '#E2E7FF',
    surfaceContainerLowest: '#FFFFFF',
    surfaceContainerHighest: '#DAE2FD',
    surfaceDim: '#D2D9F4',
    onSurface: '#131B2E',
    onSurfaceVariant: '#434655',

    error: '#BA1A1A',
    errorContainer: '#FFDAD6',
    onError: '#FFFFFF',

    outline: '#737686',
    outlineVariant: '#C3C6D7',

    inverseSurface: '#283044',
    inverseOnSurface: '#EEF0FF',

    // Legacy aliases
    canvas: '#FAF8FF',
    border: '#C3C6D7',
    textPrimary: '#131B2E',
    textMuted: '#434655',
    white: '#FFFFFF',
    focusRing: 'rgba(37, 99, 235, 0.15)',
  },
  fonts: {
    regular: 'Inter_400Regular',
    medium: 'Inter_500Medium',
    semiBold: 'Inter_600SemiBold',
    bold: 'Inter_700Bold',
  },
  fontSize: {
    xs: 10,
    sm: 12,
    md: 14,
    base: 16,
    lg: 20,
    xl: 24,
    xxl: 32,
  },
  lineHeight: {
    xs: 14,
    sm: 16,
    md: 20,
    base: 24,
    lg: 28,
    xl: 32,
    xxl: 40,
  },
  spacing: {
    xs: 4,
    sm: 8,
    md: 16,
    lg: 24,
    xl: 32,
  },
  radii: {
    sm: 4,
    md: 8,
    lg: 12,
    xl: 16,
    xxl: 20,
    input: 12,
    button: 16,
    card: 16,
    pill: 9999,
  },
  dimensions: {
    buttonHeight: 56,
    inputHeight: 50,
    minTouchTarget: 44,
    headerHeight: 64,
  },
  shadow: {
    sm: {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 1 },
      shadowOpacity: 0.06,
      shadowRadius: 4,
      elevation: 1,
    },
    md: {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 2 },
      shadowOpacity: 0.1,
      shadowRadius: 8,
      elevation: 3,
    },
    lg: {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 4 },
      shadowOpacity: 0.12,
      shadowRadius: 16,
      elevation: 6,
    },
  },
};

export default theme;
