import React from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import theme from '../config/theme';

export default function PrimaryButton({ title, onPress, loading, disabled, showArrow }) {
  const isDisabled = disabled || loading;

  return (
    <Pressable
      onPress={onPress}
      disabled={isDisabled}
      style={({ pressed }) => [
        styles.button,
        pressed && !isDisabled && styles.pressed,
        isDisabled && styles.disabled,
      ]}
      accessibilityLabel={title}
      accessibilityRole="button"
    >
      {loading ? (
        <ActivityIndicator color={theme.colors.white} size="small" />
      ) : (
        <View style={styles.content}>
          <Text style={styles.text}>{title}</Text>
          {showArrow && (
            <MaterialIcons
              name="arrow-forward"
              size={20}
              color={theme.colors.onPrimary}
            />
          )}
        </View>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    height: theme.dimensions.buttonHeight,
    borderRadius: theme.radii.button,
    backgroundColor: theme.colors.primaryContainer,
    alignItems: 'center',
    justifyContent: 'center',
    ...theme.shadow.md,
  },
  pressed: {
    backgroundColor: theme.colors.primary,
    transform: [{ scale: 0.98 }],
  },
  disabled: {
    opacity: 0.5,
  },
  content: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  text: {
    color: theme.colors.onPrimary,
    fontFamily: theme.fonts.semiBold,
    fontSize: theme.fontSize.base,
    lineHeight: theme.lineHeight.base,
    letterSpacing: 0.16,
  },
});
