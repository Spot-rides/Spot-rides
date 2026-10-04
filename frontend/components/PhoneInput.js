import React from 'react';
import { StyleSheet, Text, TextInput, View } from 'react-native';
import theme from '../config/theme';
import { DIAL_CODE, PHONE_LENGTH } from '../config/constants';

export default function PhoneInput({ value, onChangeText, error }) {
  const handleChange = (text) => {
    const digits = text.replace(/\D/g, '').slice(0, PHONE_LENGTH);
    onChangeText(digits);
  };

  return (
    <View>
      <View style={[styles.container, error && styles.containerError]}>
        <View style={styles.prefix}>
          <Text style={styles.flag}>🇮🇳</Text>
          <Text style={styles.dialCode}>{DIAL_CODE}</Text>
        </View>
        <View style={styles.separator} />
        <TextInput
          style={styles.input}
          value={value}
          onChangeText={handleChange}
          placeholder="Enter mobile number"
          placeholderTextColor={theme.colors.textMuted}
          keyboardType="number-pad"
          maxLength={PHONE_LENGTH}
          accessibilityLabel="Phone number"
        />
      </View>
      {error ? <Text style={styles.errorText}>{error}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    height: theme.dimensions.inputHeight,
    borderRadius: theme.radii.input,
    borderWidth: 1.5,
    borderColor: theme.colors.border,
    backgroundColor: theme.colors.surface,
    overflow: 'hidden',
  },
  containerError: {
    borderColor: theme.colors.error,
  },
  prefix: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: theme.spacing.sm + 4,
    gap: theme.spacing.xs,
  },
  flag: {
    fontSize: 20,
  },
  dialCode: {
    fontFamily: theme.fonts.semiBold,
    fontSize: theme.fontSize.base,
    color: theme.colors.textPrimary,
  },
  separator: {
    width: 1,
    height: 24,
    backgroundColor: theme.colors.border,
  },
  input: {
    flex: 1,
    height: '100%',
    paddingHorizontal: theme.spacing.sm + 4,
    fontFamily: theme.fonts.regular,
    fontSize: theme.fontSize.base,
    color: theme.colors.textPrimary,
  },
  errorText: {
    color: theme.colors.error,
    fontFamily: theme.fonts.regular,
    fontSize: theme.fontSize.sm,
    marginTop: theme.spacing.xs,
    marginLeft: theme.spacing.xs,
  },
});
