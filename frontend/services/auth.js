import api from './api';

export async function requestOtp(phoneE164) {
  return api.post('/api/auth/otp/request/', { phone_number: phoneE164 });
}

export async function verifyOtp(phoneE164, code) {
  return api.post('/api/auth/otp/verify/', { phone_number: phoneE164, code });
}

export async function refreshToken(refreshJwt) {
  return api.post('/api/auth/token/refresh/', { refresh: refreshJwt });
}

export async function logout(refreshJwt) {
  return api.post('/api/auth/logout/', { refresh: refreshJwt });
}
