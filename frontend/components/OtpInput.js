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
          return (
            <View
              key={i}
              style={[
                styles.box,
                isActive && styles.boxActive,
                error && styles.boxError,
              ]}
            >
              <Text style={styles.digit}>{isFilled ? digits[i] : ''}</Text>
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

const BOX_SIZE = 48;

const styles = StyleSheet.create({
  boxRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: theme.spacing.sm + 2,
  },
  box: {
    width: BOX_SIZE,
    height: BOX_SIZE + 8,
    borderRadius: theme.radii.input,
    borderWidth: 1.5,
    borderColor: theme.colors.border,
    backgroundColor: theme.colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  boxActive: {
    borderColor: theme.colors.primary,
    borderWidth: 2,
  },
  boxError: {
    borderColor: theme.colors.error,
  },
  digit: {
    fontFamily: theme.fonts.bold,
    fontSize: theme.fontSize.xl,
    color: theme.colors.textPrimary,
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
    marginTop: theme.spacing.sm,
    textAlign: 'center',
  },
});
