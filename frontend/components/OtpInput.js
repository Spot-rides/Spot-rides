import React, { useRef } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import theme from '../config/theme';
import { OTP_LENGTH } from '../config/constants';

export default function OtpInput({ value, onChangeText, error }) {
  const inputRef = useRef(null);

  const handleChange = (text) => {
    const digits = text.replace(/\D/g, '').slice(0, OTP_LENGTH);
    onChangeText(digits);
  };

  const handlePress = () => {
    inputRef.current?.focus();
  };

  const digits = value.split('');

  return (
    <View>
      <Pressable onPress={handlePress} style={styles.boxRow}>
        {Array.from({ length: OTP_LENGTH }).map((_, i) => {
          const isFilled = i < digits.length;
          const isActive = i === digits.length;
          const isEmpty = i > digits.length;

          return (
            <View
              key={i}
              style={[
                styles.box,
                isFilled && styles.boxFilled,
                isActive && styles.boxActive,
                error && styles.boxError,
              ]}
            >
              {isFilled ? (
                <Text style={styles.digit}>{digits[i]}</Text>
              ) : isActive ? (
                <View style={styles.cursor} />
              ) : (
                <View style={styles.dot} />
              )}
            </View>
          );
        })}
      </Pressable>
      <TextInput
        ref={inputRef}
        value={value}
        onChangeText={handleChange}
        keyboardType="number-pad"
        maxLength={OTP_LENGTH}
        style={styles.hiddenInput}
        autoFocus
        accessibilityLabel="OTP code"
      />
      {error ? <Text style={styles.errorText}>{error}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  boxRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 8,
  },
  box: {
    width: 48,
    height: 56,
    borderRadius: theme.radii.lg,
    backgroundColor: theme.colors.surfaceContainerHigh,
    alignItems: 'center',
    justifyContent: 'center',
  },
  boxFilled: {
    backgroundColor: theme.colors.surfaceContainerLowest,
    ...theme.shadow.sm,
  },
  boxActive: {
    backgroundColor: theme.colors.surfaceContainerLowest,
    borderWidth: 2,
    borderColor: theme.colors.primaryContainer,
    ...theme.shadow.md,
  },
  boxError: {
    borderWidth: 1.5,
    borderColor: theme.colors.error,
  },
  digit: {
    fontFamily: theme.fonts.bold,
    fontSize: theme.fontSize.xl,
    lineHeight: theme.lineHeight.xl,
    color: theme.colors.onSurface,
  },
  cursor: {
    width: 2,
    height: 24,
    borderRadius: 1,
    backgroundColor: theme.colors.primaryContainer,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: theme.colors.outlineVariant,
  },
  hiddenInput: {
    position: 'absolute',
    opacity: 0,
    height: 0,
    width: 0,
  },
  errorText: {
    color: theme.colors.error,
    fontFamily: theme.fonts.regular,
    fontSize: theme.fontSize.sm,
    marginTop: 12,
    textAlign: 'center',
  },
});
