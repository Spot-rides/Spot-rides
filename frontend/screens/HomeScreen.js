import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import theme from '../config/theme';
import { useAuth } from '../context/AuthContext';
import PrimaryButton from '../components/PrimaryButton';

export default function HomeScreen() {
  const { user, signOut } = useAuth();
  const [loggingOut, setLoggingOut] = React.useState(false);

  const handleLogout = async () => {
    setLoggingOut(true);
    await signOut();
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Welcome to Spot Rides</Text>
      {user?.phone_number ? (
        <Text style={styles.phone}>{user.phone_number}</Text>
      ) : null}
      <View style={styles.buttonWrapper}>
        <PrimaryButton
          title="Log Out"
          onPress={handleLogout}
          loading={loggingOut}
        />
      </View>
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
  title: {
    fontFamily: theme.fonts.bold,
    fontSize: theme.fontSize.xl,
    color: theme.colors.textPrimary,
    marginBottom: theme.spacing.sm,
  },
  phone: {
    fontFamily: theme.fonts.regular,
    fontSize: theme.fontSize.base,
    color: theme.colors.textMuted,
    marginBottom: theme.spacing.xl,
  },
  buttonWrapper: {
    width: '100%',
    maxWidth: 300,
  },
});
