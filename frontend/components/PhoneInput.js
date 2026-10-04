import React from 'react';
import { StyleSheet, Text, TextInput, View } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import theme from '../config/theme';
import { DIAL_CODE, PHONE_LENGTH } from '../config/constants';

function formatPhone(digits) {
  if (digits.length <= 5) return digits;
  return digits.slice(0, 5) + ' ' + digits.slice(5);
}

export default function PhoneInput({ value, onChangeText, error }) {
  const handleChange = (text) => {
    const digits = text.replace(/\D/g, '').slice(0, PHONE_LENGTH);
    onChangeText(digits);
  };

  const isValid = value.length === PHONE_LENGTH;

  return (
    <View>
      <View style={[styles.container, error && styles.containerError]}>
        <View style={styles.prefix}>
          <Text style={styles.flag}>🇮🇳</Text>
          <Text style={styles.dialCode}>{DIAL_CODE}</Text>
          <MaterialIcons
            name="expand-more"
            size={18}
            color={theme.colors.onSurfaceVariant}
          />
        </View>
        <View style={styles.separator} />
        <TextInput
          style={styles.input}
          value={formatPhone(value)}
          onChangeText={handleChange}
          placeholder="98765 43210"
          placeholderTextColor={theme.colors.outline}
          keyboardType="number-pad"
          maxLength={14}
          accessibilityLabel="Phone number"
        />
      </View>
      {isValid && !error && (
        <View style={styles.validationPill}>
          <MaterialIcons name="check-circle" size={16} color={theme.colors.secondary} />
          <Text style={styles.validationText}>
            Valid 10-digit Indian mobile number (+91) detected
          </Text>
        </View>
      )}
      {error ? <Text style={styles.errorText}>{error}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    height: theme.dimensions.inputHeight,
    borderRadius: theme.radii.lg,
    backgroundColor: theme.colors.surfaceContainerLow,
    paddingHorizontal: 12,
    overflow: 'hidden',
  },
  containerError: {
    borderWidth: 1.5,
    borderColor: theme.colors.error,
  },
  prefix: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingRight: 10,
    paddingVertical: 6,
  },
  flag: {
    fontSize: 20,
  },
  dialCode: {
    fontFamily: theme.fonts.semiBold,
    fontSize: theme.fontSize.md,
    color: theme.colors.onSurface,
  },
  separator: {
    width: 1,
    height: 24,
    backgroundColor: theme.colors.outlineVariant,
    marginRight: 4,
  },
  input: {
    flex: 1,
    height: '100%',
    paddingHorizontal: 10,
    fontFamily: theme.fonts.semiBold,
    fontSize: theme.fontSize.lg,
    lineHeight: theme.lineHeight.lg,
    color: theme.colors.onSurface,
    letterSpacing: 0.5,
  },
  validationPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 8,
  },
  validationText: {
    fontFamily: theme.fonts.semiBold,
    fontSize: theme.fontSize.sm,
    color: theme.colors.secondary,
  },
  errorText: {
    color: theme.colors.error,
    fontFamily: theme.fonts.regular,
    fontSize: theme.fontSize.sm,
    marginTop: 8,
    marginLeft: 4,
  },
});
