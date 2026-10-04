import React from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text } from 'react-native';
import theme from '../config/theme';

export default function PrimaryButton({ title, onPress, loading, disabled }) {
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
        <Text style={styles.text}>{title}</Text>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    height: theme.dimensions.buttonHeight,
    borderRadius: theme.radii.button,
    backgroundColor: theme.colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    minWidth: theme.dimensions.minTouchTarget,
    minHeight: theme.dimensions.minTouchTarget,
  },
  pressed: {
    backgroundColor: theme.colors.primaryDark,
  },
  disabled: {
    opacity: 0.5,
  },
  text: {
    color: theme.colors.white,
    fontFamily: theme.fonts.semiBold,
    fontSize: theme.fontSize.base,
    lineHeight: theme.lineHeight.base,
  },
});
