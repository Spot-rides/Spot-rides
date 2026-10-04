export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export const SPLASH_MIN_DISPLAY_MS = 2000;

export const DIAL_CODE = '+91';

export const OTP_LENGTH = 6;

export const PHONE_LENGTH = 10;

export const STORAGE_KEYS = {
  ACCESS_TOKEN: 'spot_rides_access_token',
  REFRESH_TOKEN: 'spot_rides_refresh_token',
  USER: 'spot_rides_user',
  IS_NEW_USER: 'spot_rides_is_new_user',
};
