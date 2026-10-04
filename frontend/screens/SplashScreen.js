import { useEffect } from 'react';
import { Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import theme from '../config/theme';
import * as secureStore from '../services/secureStore';
import { refreshToken } from '../services/auth';
import { useAuth } from '../context/AuthContext';

const HERO_IMAGE_URI =
  'https://lh3.googleusercontent.com/aida-public/AB6AXuDf0sZKRXfzDionK3J7WFholR0wgaNzSvde0m4_st0BSbXdASaoh_3rH6y5KzEQNC-n8YxnCUTx7C_P8nu8Yxa_HT3Iyc3rXZrhRcX_RN815_98OpFmC6Uy9lNZDycn9ooU3RT7DNlSziiecfYZc-5ZcXJK-QBSAGpCWheAACG9AhDFnZeUOkXSwltGTHjoq5u1mXsdRK6VSz5re9ZLs3GzV1_UkdDVHngCP9R6nF6NHZRe61v8-Os0TA';

export default function SplashScreen({ navigation }) {
  const { restoreSession } = useAuth();
  const insets = useSafeAreaInsets();

  useEffect(() => {
    let mounted = true;
    const tryRestore = async () => {
      try {
        const stored = await secureStore.getRefreshToken();
        if (!stored || !mounted) return;
        const data = await refreshToken(stored);
        const newAccess = data.access;
        const newRefresh = data.refresh || stored;
        await secureStore.setTokens(newAccess, newRefresh);
        const userInfo = await secureStore.getUser();
        if (userInfo && mounted) {
          restoreSession({
            user: userInfo.user,
            isNewUser: userInfo.isNewUser,
            accessToken: newAccess,
          });
        }
      } catch {
        await secureStore.clearAll().catch(() => {});
      }
    };
    tryRestore();
    return () => {
      mounted = false;
    };
  }, [restoreSession]);

  return (
    <View style={[styles.screen, { paddingTop: insets.top }]}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Logo with glow */}
        <View style={styles.logoSection}>
          <View style={styles.logoWrapper}>
            <View style={styles.logoGlow} />
            <View style={styles.logoBox}>
              <Image
                source={require('../assets/icon.png')}
                style={styles.logoImage}
                resizeMode="contain"
              />
            </View>
          </View>
          <Text style={styles.appTitle}>SPOT RIDES</Text>
          <View style={styles.taglinePill}>
            <MaterialIcons
              name="navigation"
              size={16}
              color={theme.colors.primaryContainer}
            />
            <Text style={styles.taglineText}>Spot to Spot Rides</Text>
          </View>
        </View>

        {/* Feature card */}
        <View style={styles.featureCard}>
          <View style={styles.heroContainer}>
            <Image
              source={{ uri: HERO_IMAGE_URI }}
              style={styles.heroImage}
              resizeMode="cover"
            />
            <View style={styles.techBadge}>
              <MaterialCommunityIcons
                name="lightning-bolt"
                size={14}
                color={theme.colors.secondary}
              />
              <Text style={styles.techBadgeText}>Tech Corridor Express</Text>
            </View>
            <View style={styles.ecoBadge}>
              <MaterialCommunityIcons
                name="leaf"
                size={14}
                color={theme.colors.onSecondaryContainer}
              />
              <Text style={styles.ecoBadgeText}>-4.2kg CO₂/ride</Text>
            </View>
          </View>

          <View style={styles.corridorPill}>
            <MaterialCommunityIcons
              name="flash"
              size={15}
              color={theme.colors.primaryContainer}
            />
            <Text style={styles.corridorText}>
              Fast Daily Office & Campus Corridors
            </Text>
          </View>

          <View style={styles.verifiedRow}>
            <MaterialCommunityIcons
              name="shield-check"
              size={18}
              color={theme.colors.secondary}
            />
            <Text style={styles.verifiedText}>
              100% Verified Corporate & College Commuters
            </Text>
          </View>
        </View>
      </ScrollView>

      {/* Bottom CTA */}
      <View style={[styles.bottomSection, { paddingBottom: Math.max(insets.bottom, 16) }]}>
        <Pressable
          style={({ pressed }) => [
            styles.getStartedBtn,
            pressed && styles.getStartedPressed,
          ]}
          onPress={() => navigation.navigate('PhoneLogin')}
          accessibilityRole="button"
          accessibilityLabel="Get Started"
        >
          <Text style={styles.getStartedText}>Get Started</Text>
          <MaterialIcons
            name="arrow-forward"
            size={20}
            color={theme.colors.onPrimary}
          />
        </Pressable>

        <Pressable
          style={styles.loginRow}
          onPress={() => navigation.navigate('PhoneLogin')}
          accessibilityRole="button"
        >
          <Text style={styles.loginLabel}>Already have an account?</Text>
          <Text style={styles.loginLink}> Log in</Text>
        </Pressable>

        <View style={styles.footerRow}>
          <MaterialCommunityIcons
            name="lock"
            size={14}
            color={theme.colors.outline}
          />
          <Text style={styles.footerText}>
            v2.4.0 • Enterprise Trust & Safety Encrypted
          </Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: theme.colors.surface,
  },
  scrollContent: {
    flexGrow: 1,
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 8,
  },
  logoSection: {
    alignItems: 'center',
    marginBottom: 24,
  },
  logoWrapper: {
    marginBottom: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoGlow: {
    position: 'absolute',
    width: 110,
    height: 110,
    borderRadius: 55,
    backgroundColor: theme.colors.primaryFixed,
    opacity: 0.6,
  },
  logoBox: {
    width: 84,
    height: 84,
    borderRadius: 12,
    backgroundColor: theme.colors.surfaceContainerLowest,
    padding: 8,
    alignItems: 'center',
    justifyContent: 'center',
    ...theme.shadow.lg,
  },
  logoImage: {
    width: '100%',
    height: '100%',
    borderRadius: 8,
  },
  appTitle: {
    fontFamily: theme.fonts.bold,
    fontSize: theme.fontSize.xl,
    lineHeight: theme.lineHeight.xl,
    color: theme.colors.onSurface,
    letterSpacing: -0.36,
    marginBottom: 8,
  },
  taglinePill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: theme.radii.pill,
    backgroundColor: theme.colors.surfaceContainerHigh,
  },
  taglineText: {
    fontFamily: theme.fonts.semiBold,
    fontSize: theme.fontSize.sm,
    lineHeight: theme.lineHeight.sm,
    color: theme.colors.primaryContainer,
  },
  featureCard: {
    backgroundColor: theme.colors.surfaceContainerLowest,
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    ...theme.shadow.sm,
  },
  heroContainer: {
    width: '100%',
    height: 176,
    borderRadius: 8,
    overflow: 'hidden',
    backgroundColor: theme.colors.surfaceContainerLow,
  },
  heroImage: {
    width: '100%',
    height: '100%',
  },
  techBadge: {
    position: 'absolute',
    top: 10,
    left: 10,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: theme.radii.pill,
    backgroundColor: theme.colors.surfaceContainerLowest,
    ...theme.shadow.sm,
  },
  techBadgeText: {
    fontFamily: theme.fonts.bold,
    fontSize: theme.fontSize.xs,
    lineHeight: theme.lineHeight.xs,
    color: theme.colors.onSurface,
  },
  ecoBadge: {
    position: 'absolute',
    bottom: 10,
    right: 10,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: theme.radii.pill,
    backgroundColor: theme.colors.secondaryContainer,
    ...theme.shadow.sm,
  },
  ecoBadgeText: {
    fontFamily: theme.fonts.semiBold,
    fontSize: theme.fontSize.xs,
    lineHeight: theme.lineHeight.xs,
    color: theme.colors.onSecondaryContainer,
  },
  corridorPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 12,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: theme.radii.pill,
    backgroundColor: theme.colors.surfaceContainer,
  },
  corridorText: {
    fontFamily: theme.fonts.semiBold,
    fontSize: theme.fontSize.sm,
    lineHeight: theme.lineHeight.sm,
    color: theme.colors.onSurface,
  },
  verifiedRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 10,
  },
  verifiedText: {
    fontFamily: theme.fonts.semiBold,
    fontSize: theme.fontSize.sm,
    lineHeight: theme.lineHeight.sm,
    color: theme.colors.secondary,
  },
  bottomSection: {
    paddingHorizontal: 20,
    paddingTop: 8,
    gap: 12,
  },
  getStartedBtn: {
    height: 56,
    borderRadius: 12,
    backgroundColor: theme.colors.primary,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    ...theme.shadow.md,
  },
  getStartedPressed: {
    backgroundColor: theme.colors.primaryContainer,
    transform: [{ scale: 0.99 }],
  },
  getStartedText: {
    color: theme.colors.onPrimary,
    fontFamily: theme.fonts.semiBold,
    fontSize: theme.fontSize.base,
    lineHeight: theme.lineHeight.base,
  },
  loginRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
  },
  loginLabel: {
    fontFamily: theme.fonts.semiBold,
    fontSize: theme.fontSize.md,
    lineHeight: theme.lineHeight.md,
    color: theme.colors.onSurfaceVariant,
  },
  loginLink: {
    fontFamily: theme.fonts.semiBold,
    fontSize: theme.fontSize.md,
    lineHeight: theme.lineHeight.md,
    color: theme.colors.primaryContainer,
  },
  footerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingBottom: 4,
  },
  footerText: {
    fontFamily: theme.fonts.bold,
    fontSize: theme.fontSize.xs,
    lineHeight: theme.lineHeight.xs,
    color: theme.colors.outline,
    letterSpacing: 0.4,
  },
});
