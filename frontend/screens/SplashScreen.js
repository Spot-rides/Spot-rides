import { useEffect } from 'react';
import { Image, StyleSheet, Text, View } from 'react-native';
import theme from '../config/theme';
import { SPLASH_MIN_DISPLAY_MS } from '../config/constants';
import * as secureStore from '../services/secureStore';
import { refreshToken } from '../services/auth';
import { useAuth } from '../context/AuthContext';

export default function SplashScreen({ navigation }) {
  const { restoreSession } = useAuth();

  useEffect(() => {
    let mounted = true;

    const run = async () => {
      const timerPromise = new Promise((resolve) =>
        setTimeout(resolve, SPLASH_MIN_DISPLAY_MS),
      );

      let authenticated = false;
      let sessionData = null;

      try {
        const stored = await secureStore.getRefreshToken();
        if (stored) {
          const data = await refreshToken(stored);
          const newAccess = data.access;
          const newRefresh = data.refresh || stored;
          await secureStore.setTokens(newAccess, newRefresh);

          const userInfo = await secureStore.getUser();
          if (userInfo) {
            sessionData = {
              user: userInfo.user,
              isNewUser: userInfo.isNewUser,
              accessToken: newAccess,
            };
            authenticated = true;
          }
        }
      } catch {
        await secureStore.clearAll().catch(() => {});
      }

      await timerPromise;

      if (!mounted) return;

      if (authenticated && sessionData) {
        restoreSession(sessionData);
      } else {
        navigation.replace('PhoneLogin');
      }
    };

    run();

    return () => {
      mounted = false;
    };
  }, [navigation, restoreSession]);

  return (
    <View style={styles.container}>
      <Image
        source={require('../assets/icon.png')}
        style={styles.logo}
        resizeMode="contain"
      />
      <Text style={styles.title}>Spot Rides</Text>
      <Text style={styles.subtitle}>Your daily commute, simplified</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.canvas,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: theme.spacing.md,
  },
  logo: {
    width: 100,
    height: 100,
    marginBottom: theme.spacing.lg,
  },
  title: {
    fontFamily: theme.fonts.bold,
    fontSize: theme.fontSize.xxl,
    color: theme.colors.textPrimary,
    marginBottom: theme.spacing.xs,
  },
  subtitle: {
    fontFamily: theme.fonts.regular,
    fontSize: theme.fontSize.base,
    color: theme.colors.textMuted,
  },
});
