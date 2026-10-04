import React, { useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import theme from '../config/theme';
import { DIAL_CODE, PHONE_LENGTH } from '../config/constants';
import { requestOtp } from '../services/auth';
import ScreenHeader from '../components/ScreenHeader';
import PhoneInput from '../components/PhoneInput';
import PrimaryButton from '../components/PrimaryButton';

const ERROR_MESSAGES = {
  invalid_phone_number: 'Please enter a valid phone number.',
  rate_limited:
    'Too many attempts. Please try again in {retry_after} seconds.',
  sms_dispatch_failed: 'Unable to send SMS. Please try again.',
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
    <View style={styles.screen}>
      <ScreenHeader
        title="Phone Login"
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
          {/* Step badge row */}
          <View style={styles.badgeRow}>
            <View style={styles.stepBadge}>
              <View style={styles.pulseDot} />
              <Text style={styles.stepText}>Step 1 of 5 • Quick Access</Text>
            </View>
            <View style={styles.encryptBadge}>
              <MaterialCommunityIcons
                name="shield-check"
                size={14}
                color={theme.colors.secondary}
              />
              <Text style={styles.encryptText}>256-Bit Encrypted</Text>
            </View>
          </View>

          {/* Headlines */}
          <View style={styles.headlines}>
            <Text style={styles.title}>Welcome to SPOT RIDES</Text>
            <Text style={styles.subtitle}>
              Enter your mobile number to get started or log in to your verified
              commuter profile.
            </Text>
          </View>

          {/* Input card */}
          <View style={styles.inputCard}>
            <Text style={styles.inputLabel}>Mobile Phone Number</Text>
            <PhoneInput value={phone} onChangeText={setPhone} error={error} />

            {/* Trust bullets */}
            <View style={styles.trustSection}>
              <View style={styles.trustRow}>
                <MaterialCommunityIcons
                  name="lock"
                  size={18}
                  color={theme.colors.primaryContainer}
                />
                <Text style={styles.trustText}>
                  Instant 6-digit secure OTP delivery via SMS & WhatsApp
                </Text>
              </View>
              <View style={styles.trustRow}>
                <MaterialCommunityIcons
                  name="shield"
                  size={18}
                  color={theme.colors.secondary}
                />
                <Text style={styles.trustText}>
                  No spam, your number is never shared with co-riders
                </Text>
              </View>
            </View>
          </View>

          {/* Send OTP button */}
          <View style={styles.ctaSection}>
            <PrimaryButton
              title="Send OTP"
              onPress={handleSendOtp}
              loading={isLoading}
              disabled={!canSubmit}
              showArrow
            />

            <Text style={styles.termsText}>
              By continuing, you agree to SPOT RIDES{' '}
              <Text style={styles.termsLink}>Terms of Service</Text> and{' '}
              <Text style={styles.termsLink}>Privacy Policy</Text>.
            </Text>
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
  badgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 16,
    marginTop: 8,
  },
  stepBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: theme.radii.pill,
    backgroundColor: theme.colors.surfaceContainerHigh,
  },
  pulseDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: theme.colors.primaryContainer,
  },
  stepText: {
    fontFamily: theme.fonts.semiBold,
    fontSize: theme.fontSize.sm,
    lineHeight: theme.lineHeight.sm,
    color: theme.colors.primaryContainer,
    letterSpacing: 0.2,
  },
  encryptBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: theme.radii.pill,
    backgroundColor: 'rgba(124, 249, 148, 0.2)',
  },
  encryptText: {
    fontFamily: theme.fonts.bold,
    fontSize: theme.fontSize.xs,
    lineHeight: theme.lineHeight.xs,
    color: theme.colors.secondary,
  },
  headlines: {
    marginBottom: 24,
    gap: 6,
  },
  title: {
    fontFamily: theme.fonts.bold,
    fontSize: theme.fontSize.xl,
    lineHeight: theme.lineHeight.xl,
    color: theme.colors.onSurface,
    letterSpacing: -0.36,
  },
  subtitle: {
    fontFamily: theme.fonts.regular,
    fontSize: theme.fontSize.md,
    lineHeight: theme.lineHeight.md,
    color: theme.colors.onSurfaceVariant,
  },
  inputCard: {
    backgroundColor: theme.colors.surfaceContainerLowest,
    borderRadius: 20,
    padding: 20,
    gap: 16,
    ...theme.shadow.sm,
  },
  inputLabel: {
    fontFamily: theme.fonts.semiBold,
    fontSize: theme.fontSize.md,
    lineHeight: theme.lineHeight.md,
    color: theme.colors.onSurface,
  },
  trustSection: {
    backgroundColor: theme.colors.surfaceContainerLow,
    borderRadius: 12,
    padding: 14,
    gap: 10,
  },
  trustRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
  },
  trustText: {
    flex: 1,
    fontFamily: theme.fonts.regular,
    fontSize: theme.fontSize.sm,
    lineHeight: theme.lineHeight.sm,
    color: theme.colors.onSurfaceVariant,
  },
  ctaSection: {
    marginTop: 'auto',
    paddingTop: 16,
    gap: 12,
  },
  termsText: {
    fontFamily: theme.fonts.regular,
    fontSize: theme.fontSize.sm,
    lineHeight: theme.lineHeight.sm,
    color: theme.colors.onSurfaceVariant,
    textAlign: 'center',
    paddingHorizontal: 8,
  },
  termsLink: {
    fontFamily: theme.fonts.semiBold,
    color: theme.colors.primaryContainer,
    textDecorationLine: 'underline',
  },
});
