import axios from 'axios';
import { API_BASE_URL } from '../config/constants';
import * as secureStore from './secureStore';

let accessToken = null;
let signOutCallback = null;
let isRefreshing = false;
let failedRequestQueue = [];

export function setAccessToken(token) {
  accessToken = token;
}

export function setSignOutCallback(fn) {
  signOutCallback = fn;
}

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => {
    if (response.status === 204 || response.status === 205) {
      return null;
    }
    const body = response.data;
    if (body && body.success === true) {
      return body.data;
    }
    return body;
  },
  async (error) => {
    if (!error.response) {
      const networkError = new Error(
        'Connection failed. Please check your internet and try again.',
      );
      networkError.code = 'network_error';
      networkError.httpStatus = null;
      throw networkError;
    }

    const { response } = error;
    const originalRequest = error.config;

    if (
      response.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url.includes('/api/auth/token/refresh/') &&
      !originalRequest.url.includes('/api/auth/logout/')
    ) {
      originalRequest._retry = true;

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedRequestQueue.push({ resolve, reject });
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return api(originalRequest);
        });
      }

      isRefreshing = true;

      try {
        const refreshToken = await secureStore.getRefreshToken();
        if (!refreshToken) {
          throw new Error('No refresh token');
        }

        const refreshResponse = await axios.post(
          `${API_BASE_URL}/api/auth/token/refresh/`,
          { refresh: refreshToken },
          { headers: { 'Content-Type': 'application/json' }, timeout: 15000 },
        );

        const data = refreshResponse.data?.data || refreshResponse.data;
        const newAccess = data.access;
        const newRefresh = data.refresh || refreshToken;

        await secureStore.setTokens(newAccess, newRefresh);
        setAccessToken(newAccess);

        failedRequestQueue.forEach(({ resolve }) => resolve(newAccess));
        failedRequestQueue = [];

        originalRequest.headers.Authorization = `Bearer ${newAccess}`;
        return api(originalRequest);
      } catch {
        failedRequestQueue.forEach(({ reject }) =>
          reject(new Error('Token refresh failed')),
        );
        failedRequestQueue = [];
        await secureStore.clearAll();
        setAccessToken(null);
        if (signOutCallback) signOutCallback();
        const authError = new Error('Session expired. Please sign in again.');
        authError.code = 'session_expired';
        throw authError;
      } finally {
        isRefreshing = false;
      }
    }

    const body = response.data;
    const apiError = new Error(
      body?.message || body?.error?.detail || 'Request failed',
    );
    apiError.code = body?.error?.code || 'unknown_error';
    apiError.detail = body?.error?.detail || null;
    apiError.fields = body?.error?.fields || null;
    apiError.retryAfter = body?.error?.retry_after || null;
    apiError.httpStatus = response.status;
    throw apiError;
  },
);

export default api;
