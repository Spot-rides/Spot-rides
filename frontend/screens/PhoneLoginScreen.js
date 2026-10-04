import React, { useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import theme from '../config/theme';
import { DIAL_CODE, PHONE_LENGTH } from '../config/constants';
import { requestOtp } from '../services/auth';
import PhoneInput from '../components/PhoneInput';
import PrimaryButton from '../components/PrimaryButton';

const ERROR_MESSAGES = {
  invalid_phone_number: 'Please enter a valid phone number.',
  rate_limited: 'Too many attempts. Please try again in {retry_after} seconds.',
  sms_dispatch_failed: 'Unable to send SMS. Please try again.',
  network_error: 'Connection failed. Please check your internet and try again.',
};

function getErrorMessage(err) {
  if (err.code === 'rate_limited' && err.retryAfter) {
    return ERROR_MESSAGES.rate_limited.replace(
      '{retry_after}',
      String(err.retryAfter),
    );
  }
  return ERROR_MESSAGES[err.code] || err.message || 'Something went wrong. Please try again.';
}

export default function PhoneLoginScreen({ navigation }) {
  const [phone, setPhone] = useState('');
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  const canSubmit = phone.length === PHONE_LENGTH && !isLoading;

  const handleSendOtp = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await requestOtp(DIAL_CODE + phone);
      navigation.navigate('OtpVerification', {
        phone,
        resendAvailableIn: data.resend_available_in,
      });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <ScrollView
        contentContainerStyle={styles.container}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.header}>
          <Text style={styles.title}>Welcome</Text>
          <Text style={styles.subtitle}>
            Enter your mobile number to get started
          </Text>
        </View>

        <View style={styles.form}>
          <PhoneInput value={phone} onChangeText={setPhone} error={error} />
          <View style={styles.buttonSpacing} />
          <PrimaryButton
            title="Send OTP"
            onPress={handleSendOtp}
            loading={isLoading}
            disabled={!canSubmit}
          />
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: {
    flex: 1,
    backgroundColor: theme.colors.canvas,
  },
  container: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingHorizontal: theme.spacing.md,
  },
  header: {
    marginBottom: theme.spacing.xl,
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
  form: {
    width: '100%',
  },
  buttonSpacing: {
    height: theme.spacing.lg,
  },
});
