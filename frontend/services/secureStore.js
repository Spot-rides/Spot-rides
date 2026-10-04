import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';
import { STORAGE_KEYS } from '../config/constants';

const isWeb = Platform.OS === 'web';

async function getItem(key) {
  if (isWeb) {
    try { return localStorage.getItem(key); } catch { return null; }
  }
  return SecureStore.getItemAsync(key);
}

async function setItem(key, value) {
  if (isWeb) {
    try { localStorage.setItem(key, value); } catch {}
    return;
  }
  return SecureStore.setItemAsync(key, value);
}

async function deleteItem(key) {
  if (isWeb) {
    try { localStorage.removeItem(key); } catch {}
    return;
  }
  return SecureStore.deleteItemAsync(key);
}

export async function getTokens() {
  try {
    const [accessToken, refreshToken] = await Promise.all([
      getItem(STORAGE_KEYS.ACCESS_TOKEN),
      getItem(STORAGE_KEYS.REFRESH_TOKEN),
    ]);
    return { accessToken, refreshToken };
  } catch {
    return { accessToken: null, refreshToken: null };
  }
}

export async function setTokens(accessToken, refreshToken) {
  await Promise.all([
    setItem(STORAGE_KEYS.ACCESS_TOKEN, accessToken),
    setItem(STORAGE_KEYS.REFRESH_TOKEN, refreshToken),
  ]);
}

export async function getRefreshToken() {
  try {
    return await getItem(STORAGE_KEYS.REFRESH_TOKEN);
  } catch {
    return null;
  }
}

export async function getUser() {
  try {
    const [userJson, isNewUserStr] = await Promise.all([
      getItem(STORAGE_KEYS.USER),
      getItem(STORAGE_KEYS.IS_NEW_USER),
    ]);
    if (!userJson) return null;
    return {
      user: JSON.parse(userJson),
      isNewUser: isNewUserStr === 'true',
    };
  } catch {
    return null;
  }
}

export async function setUser(user, isNewUser) {
  await Promise.all([
    setItem(STORAGE_KEYS.USER, JSON.stringify(user)),
    setItem(STORAGE_KEYS.IS_NEW_USER, String(isNewUser)),
  ]);
}

export async function clearAll() {
  const keys = Object.values(STORAGE_KEYS);
  await Promise.all(keys.map((key) => deleteItem(key).catch(() => {})));
}
