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
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import theme from '../config/theme';
import { DIAL_CODE, OTP_LENGTH } from '../config/constants';
import { requestOtp, verifyOtp } from '../services/auth';
import * as secureStore from '../services/secureStore';
import { useAuth } from '../context/AuthContext';
import ScreenHeader from '../components/ScreenHeader';
import OtpInput from '../components/OtpInput';
import PrimaryButton from '../components/PrimaryButton';

const ERROR_MESSAGES = {
  invalid_code: 'Incorrect code. Please try again.',
  code_expired: 'Code has expired. Please request a new one.',
  no_active_otp: 'No active code found. Please request a new one.',
  too_many_attempts:
    'Too many incorrect attempts. Please request a new code.',
  rate_limited:
    'Too many attempts. Please try again in {retry_after} seconds.',
  network_error:
    'Connection failed. Please check your internet and try again.',
};

function getErrorMessage(err) {
  if (err.code === 'rate_limited' && err.retryAfter) {
    return ERROR_MESSAGES.rate_limited.replace(
      '{retry_after}',
      String(err.retryAfter),
    );
  }
  return (
    ERROR_MESSAGES[err.code] ||
    err.message ||
    'Something went wrong. Please try again.'
  );
}

function formatPhoneDisplay(phone) {
  if (phone.length <= 5) return DIAL_CODE + ' ' + phone;
  return DIAL_CODE + ' ' + phone.slice(0, 5) + ' ' + phone.slice(5);
}

function formatTimer(seconds) {
  const m = String(Math.floor(seconds / 60)).padStart(2, '0');
  const s = String(seconds % 60).padStart(2, '0');
  return `${m}:${s}`;
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
    <View style={styles.screen}>
      <ScreenHeader
        title="Otp Verification"
        onBack={() => navigation.goBack()}
      />

      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {/* Progress tracker */}
          <View style={styles.progressRow}>
            <View style={styles.stepRow}>
              <View style={styles.stepCircle}>
                <Text style={styles.stepNumber}>2</Text>
              </View>
              <Text style={styles.stepLabel}>Step 2 of 5 • Verification</Text>
            </View>
            <View style={styles.dotsRow}>
              <View style={[styles.dot, styles.dotFilled]} />
              <View style={[styles.dot, styles.dotFilled]} />
              <View style={[styles.dot, styles.dotEmpty]} />
              <View style={[styles.dot, styles.dotEmpty]} />
              <View style={[styles.dot, styles.dotEmpty]} />
            </View>
          </View>

          {/* Headline & phone display */}
          <View style={styles.headlineSection}>
            <Text style={styles.title}>Enter Verification Code</Text>
            <View style={styles.phoneContext}>
              <Text style={styles.phoneLabel}>
                We have sent a 6-digit code to
              </Text>
              <View style={styles.phonePill}>
                <Text style={styles.phoneNumber}>
                  {formatPhoneDisplay(phone)}
                </Text>
                <Pressable
                  onPress={() => navigation.goBack()}
                  accessibilityLabel="Edit mobile number"
                  hitSlop={8}
                >
                  <MaterialIcons
                    name="edit"
                    size={16}
                    color={theme.colors.primaryContainer}
                  />
                </Pressable>
              </View>
            </View>
          </View>

          {/* OTP Input */}
          <View style={styles.otpSection}>
            <OtpInput value={code} onChangeText={setCode} error={error} />
          </View>

          {/* Resend card */}
          <View style={styles.resendCard}>
            <View style={styles.resendTimerRow}>
              <View style={styles.resendTimerLeft}>
                <MaterialCommunityIcons
                  name="clock-outline"
                  size={20}
                  color={theme.colors.onSurfaceVariant}
                />
                <Text style={styles.resendTimerLabel}>Resend code in</Text>
              </View>
              <View style={styles.timerBadge}>
                <Text style={styles.timerText}>
                  {formatTimer(resendTimer)}
                </Text>
              </View>
            </View>
            <Pressable
              style={({ pressed }) => [
                styles.resendBtn,
                resendTimer > 0 && styles.resendBtnDisabled,
                pressed && resendTimer === 0 && styles.resendBtnPressed,
              ]}
              onPress={handleResend}
              disabled={resendTimer > 0 || isResending}
              accessibilityLabel="Resend via SMS"
              accessibilityRole="button"
            >
              <MaterialCommunityIcons
                name="message-text"
                size={18}
                color={
                  resendTimer > 0
                    ? theme.colors.outline
                    : theme.colors.onPrimary
                }
              />
              <Text
                style={[
                  styles.resendBtnText,
                  resendTimer > 0 && styles.resendBtnTextDisabled,
                ]}
              >
                {isResending ? 'Sending...' : 'Resend via SMS'}
              </Text>
            </Pressable>
          </View>

          {/* Trust card */}
          <View style={styles.trustCard}>
            <View style={styles.trustIconCircle}>
              <MaterialCommunityIcons
                name="shield"
                size={18}
                color={theme.colors.onSecondaryContainer}
              />
            </View>
            <View style={styles.trustContent}>
              <Text style={styles.trustTitle}>Corridor Trust Guarantee</Text>
              <Text style={styles.trustDesc}>
                Your number is only verified once to securely cross-reference
                corporate domain networks and active carpools.
              </Text>
            </View>
          </View>

          {/* Verify button */}
          <View style={styles.ctaSection}>
            <PrimaryButton
              title="Verify & Proceed"
              onPress={handleVerify}
              loading={isLoading}
              disabled={!canVerify}
              showArrow
            />
            <View style={styles.footerRow}>
              <MaterialCommunityIcons
                name="lock"
                size={14}
                color={theme.colors.outline}
              />
              <Text style={styles.footerText}>
                Protected by end-to-end corridor trust protocols
              </Text>
            </View>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: theme.colors.surface,
  },
  flex: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    paddingHorizontal: 20,
    paddingBottom: 24,
  },
  progressRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingTop: 8,
    paddingBottom: 16,
  },
  stepRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  stepCircle: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: theme.colors.primaryContainer,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepNumber: {
    fontFamily: theme.fonts.bold,
    fontSize: theme.fontSize.xs,
    lineHeight: theme.lineHeight.xs,
    color: theme.colors.onPrimary,
  },
  stepLabel: {
    fontFamily: theme.fonts.semiBold,
    fontSize: theme.fontSize.sm,
    lineHeight: theme.lineHeight.sm,
    color: theme.colors.onSurfaceVariant,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  dotsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  dot: {
    height: 6,
    borderRadius: 3,
  },
  dotFilled: {
    width: 24,
    backgroundColor: theme.colors.primaryContainer,
  },
  dotEmpty: {
    width: 8,
    backgroundColor: theme.colors.surfaceContainerHighest,
  },
  headlineSection: {
    marginTop: 8,
    gap: 6,
    marginBottom: 32,
  },
  title: {
    fontFamily: theme.fonts.bold,
    fontSize: theme.fontSize.xl,
    lineHeight: theme.lineHeight.xl,
    color: theme.colors.onSurface,
    letterSpacing: -0.36,
  },
  phoneContext: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 6,
  },
  phoneLabel: {
    fontFamily: theme.fonts.regular,
    fontSize: theme.fontSize.md,
    lineHeight: theme.lineHeight.md,
    color: theme.colors.onSurfaceVariant,
  },
  phonePill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 2,
    borderRadius: theme.radii.pill,
    backgroundColor: theme.colors.surfaceContainerHigh,
  },
  phoneNumber: {
    fontFamily: theme.fonts.semiBold,
    fontSize: theme.fontSize.md,
    lineHeight: theme.lineHeight.md,
    color: theme.colors.primaryContainer,
  },
  otpSection: {
    alignItems: 'center',
    marginBottom: 32,
  },
  resendCard: {
    backgroundColor: theme.colors.surfaceContainerLow,
    borderRadius: 12,
    padding: 16,
    gap: 14,
    marginBottom: 16,
    ...theme.shadow.sm,
  },
  resendTimerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  resendTimerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  resendTimerLabel: {
    fontFamily: theme.fonts.semiBold,
    fontSize: theme.fontSize.md,
    lineHeight: theme.lineHeight.md,
    color: theme.colors.onSurfaceVariant,
  },
  timerBadge: {
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: theme.radii.pill,
    backgroundColor: theme.colors.surfaceContainerHighest,
  },
  timerText: {
    fontFamily: theme.fonts.bold,
    fontSize: theme.fontSize.md,
    lineHeight: theme.lineHeight.md,
    color: theme.colors.onSurface,
    fontVariant: ['tabular-nums'],
  },
  resendBtn: {
    height: 44,
    borderRadius: 8,
    backgroundColor: theme.colors.primaryContainer,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    ...theme.shadow.sm,
  },
  resendBtnDisabled: {
    backgroundColor: theme.colors.surfaceContainerHighest,
    opacity: 0.6,
  },
  resendBtnPressed: {
    backgroundColor: theme.colors.primary,
  },
  resendBtnText: {
    fontFamily: theme.fonts.semiBold,
    fontSize: theme.fontSize.sm,
    lineHeight: theme.lineHeight.sm,
    color: theme.colors.onPrimary,
  },
  resendBtnTextDisabled: {
    color: theme.colors.outline,
  },
  trustCard: {
    backgroundColor: theme.colors.surfaceContainerLowest,
    borderRadius: 12,
    padding: 14,
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
    marginBottom: 16,
    ...theme.shadow.sm,
  },
  trustIconCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: theme.colors.secondaryContainer,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 2,
  },
  trustContent: {
    flex: 1,
  },
  trustTitle: {
    fontFamily: theme.fonts.semiBold,
    fontSize: theme.fontSize.md,
    lineHeight: theme.lineHeight.md,
    color: theme.colors.onSurface,
    marginBottom: 2,
  },
  trustDesc: {
    fontFamily: theme.fonts.regular,
    fontSize: theme.fontSize.sm,
    lineHeight: theme.lineHeight.sm,
    color: theme.colors.onSurfaceVariant,
  },
  ctaSection: {
    marginTop: 'auto',
    paddingTop: 16,
    gap: 10,
  },
  footerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
  },
  footerText: {
    fontFamily: theme.fonts.bold,
    fontSize: theme.fontSize.xs,
    lineHeight: theme.lineHeight.xs,
    color: theme.colors.outline,
  },
});
