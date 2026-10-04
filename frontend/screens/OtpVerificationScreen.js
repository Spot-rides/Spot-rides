import React, { useCallback, useEffect, useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import theme from '../config/theme';
import { DIAL_CODE, OTP_LENGTH } from '../config/constants';
import { requestOtp, verifyOtp } from '../services/auth';
import * as secureStore from '../services/secureStore';
import { useAuth } from '../context/AuthContext';
import OtpInput from '../components/OtpInput';
import PrimaryButton from '../components/PrimaryButton';

const ERROR_MESSAGES = {
  invalid_code: 'Incorrect code. Please try again.',
  code_expired: 'Code has expired. Please request a new one.',
  no_active_otp: 'No active code found. Please request a new one.',
  too_many_attempts: 'Too many incorrect attempts. Please request a new code.',
  rate_limited: 'Too many attempts. Please try again in {retry_after} seconds.',
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

function maskPhone(phone) {
  if (phone.length <= 4) return phone;
  const visible = phone.slice(-4);
  const masked = '*'.repeat(phone.length - 4);
  return `${DIAL_CODE} ${masked.replace(/(.{3})/g, '$1 ').trim()} ${visible}`;
}

export default function OtpVerificationScreen({ route, navigation }) {
  const { phone, resendAvailableIn } = route.params;
  const { signIn } = useAuth();

  const [code, setCode] = useState('');
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [resendTimer, setResendTimer] = useState(resendAvailableIn);
  const [isResending, setIsResending] = useState(false);

  useEffect(() => {
    if (resendTimer <= 0) return;
    const interval = setInterval(() => {
      setResendTimer((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [resendTimer]);

  const canVerify = code.length === OTP_LENGTH && !isLoading;

  const handleVerify = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await verifyOtp(DIAL_CODE + phone, code);
      await secureStore.setTokens(data.access, data.refresh);
      await secureStore.setUser(data.user, data.is_new_user);
      signIn({
        user: data.user,
        isNewUser: data.is_new_user,
        accessToken: data.access,
      });
    } catch (err) {
      setError(getErrorMessage(err));
      if (err.code === 'invalid_code' || err.code === 'too_many_attempts') {
        setCode('');
      }
      if (
        err.code === 'code_expired' ||
        err.code === 'no_active_otp' ||
        err.code === 'too_many_attempts'
      ) {
        setResendTimer(0);
      }
    } finally {
      setIsLoading(false);
    }
  }, [code, phone, signIn]);

  const handleResend = async () => {
    setIsResending(true);
    setError(null);
    try {
      const data = await requestOtp(DIAL_CODE + phone);
      setResendTimer(data.resend_available_in);
      setCode('');
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsResending(false);
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
        <Pressable
          onPress={() => navigation.goBack()}
          style={styles.backButton}
          accessibilityLabel="Go back"
          accessibilityRole="button"
        >
          <Text style={styles.backText}>← Edit number</Text>
        </Pressable>

        <View style={styles.header}>
          <Text style={styles.title}>Verify your number</Text>
          <Text style={styles.subtitle}>
            Code sent to {maskPhone(phone)}
          </Text>
        </View>

        <View style={styles.form}>
          <OtpInput value={code} onChangeText={setCode} error={error} />

          <View style={styles.buttonSpacing} />

          <PrimaryButton
            title="Verify"
            onPress={handleVerify}
            loading={isLoading}
            disabled={!canVerify}
          />

          <View style={styles.resendRow}>
            {resendTimer > 0 ? (
              <Text style={styles.timerText}>
                Resend code in {resendTimer}s
              </Text>
            ) : (
              <Pressable
                onPress={handleResend}
                disabled={isResending}
                accessibilityLabel="Resend code"
                accessibilityRole="button"
              >
                <Text
                  style={[
                    styles.resendText,
                    isResending && styles.resendDisabled,
                  ]}
                >
                  {isResending ? 'Sending...' : 'Resend Code'}
                </Text>
              </Pressable>
            )}
          </View>
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
    paddingHorizontal: theme.spacing.md,
    paddingTop: 60,
  },
  backButton: {
    marginBottom: theme.spacing.lg,
    minHeight: theme.dimensions.minTouchTarget,
    justifyContent: 'center',
  },
  backText: {
    fontFamily: theme.fonts.medium,
    fontSize: theme.fontSize.md,
    color: theme.colors.primary,
  },
  header: {
    marginBottom: theme.spacing.xl,
  },
  title: {
    fontFamily: theme.fonts.bold,
    fontSize: theme.fontSize.xl,
    color: theme.colors.textPrimary,
    marginBottom: theme.spacing.xs,
  },
  subtitle: {
    fontFamily: theme.fonts.regular,
    fontSize: theme.fontSize.md,
    color: theme.colors.textMuted,
  },
  form: {
    width: '100%',
  },
  buttonSpacing: {
    height: theme.spacing.lg,
  },
  resendRow: {
    marginTop: theme.spacing.lg,
    alignItems: 'center',
    minHeight: theme.dimensions.minTouchTarget,
    justifyContent: 'center',
  },
  timerText: {
    fontFamily: theme.fonts.regular,
    fontSize: theme.fontSize.md,
    color: theme.colors.textMuted,
  },
  resendText: {
    fontFamily: theme.fonts.semiBold,
    fontSize: theme.fontSize.md,
    color: theme.colors.primary,
  },
  resendDisabled: {
    opacity: 0.5,
  },
});
