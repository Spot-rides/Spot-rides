import * as SecureStore from 'expo-secure-store';
import { STORAGE_KEYS } from '../config/constants';

export async function getTokens() {
  try {
    const [accessToken, refreshToken] = await Promise.all([
      SecureStore.getItemAsync(STORAGE_KEYS.ACCESS_TOKEN),
      SecureStore.getItemAsync(STORAGE_KEYS.REFRESH_TOKEN),
    ]);
    return { accessToken, refreshToken };
  } catch {
    return { accessToken: null, refreshToken: null };
  }
}

export async function setTokens(accessToken, refreshToken) {
  await Promise.all([
    SecureStore.setItemAsync(STORAGE_KEYS.ACCESS_TOKEN, accessToken),
    SecureStore.setItemAsync(STORAGE_KEYS.REFRESH_TOKEN, refreshToken),
  ]);
}

export async function getRefreshToken() {
  try {
    return await SecureStore.getItemAsync(STORAGE_KEYS.REFRESH_TOKEN);
  } catch {
    return null;
  }
}

export async function getUser() {
  try {
    const [userJson, isNewUserStr] = await Promise.all([
      SecureStore.getItemAsync(STORAGE_KEYS.USER),
      SecureStore.getItemAsync(STORAGE_KEYS.IS_NEW_USER),
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
    SecureStore.setItemAsync(STORAGE_KEYS.USER, JSON.stringify(user)),
    SecureStore.setItemAsync(STORAGE_KEYS.IS_NEW_USER, String(isNewUser)),
  ]);
}

export async function clearAll() {
  const keys = Object.values(STORAGE_KEYS);
  await Promise.all(
    keys.map((key) => SecureStore.deleteItemAsync(key).catch(() => {})),
  );
}
