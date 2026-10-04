import React, { createContext, useContext, useEffect, useReducer } from 'react';
import * as secureStore from '../services/secureStore';
import { logout as logoutApi } from '../services/auth';
import { setAccessToken, setSignOutCallback } from '../services/api';

const AuthContext = createContext(null);

const initialState = {
  isAuthenticated: false,
  isLoading: false,
  user: null,
  isNewUser: false,
  accessToken: null,
};

function authReducer(state, action) {
  switch (action.type) {
    case 'SIGN_IN':
      return {
        ...state,
        isAuthenticated: true,
        isLoading: false,
        user: action.payload.user,
        isNewUser: action.payload.isNewUser,
        accessToken: action.payload.accessToken,
      };
    case 'SIGN_OUT':
      return {
        ...initialState,
        isLoading: false,
      };
    case 'RESTORE_SESSION':
      return {
        ...state,
        isAuthenticated: true,
        isLoading: false,
        user: action.payload.user,
        isNewUser: action.payload.isNewUser,
        accessToken: action.payload.accessToken,
      };
    case 'LOADING_COMPLETE':
      return { ...state, isLoading: false };
    default:
      return state;
  }
}

export function AuthProvider({ children }) {
  const [state, dispatch] = useReducer(authReducer, initialState);

  useEffect(() => {
    const handleForceSignOut = () => {
      dispatch({ type: 'SIGN_OUT' });
      setAccessToken(null);
    };
    setSignOutCallback(handleForceSignOut);
  }, []);

  const signIn = ({ user, isNewUser, accessToken }) => {
    setAccessToken(accessToken);
    dispatch({
      type: 'SIGN_IN',
      payload: { user, isNewUser, accessToken },
    });
  };

  const signOut = async () => {
    try {
      const refreshToken = await secureStore.getRefreshToken();
      if (refreshToken) {
        await logoutApi(refreshToken).catch(() => {});
      }
    } catch {
      // Ignore — we clear local state regardless
    }
    await secureStore.clearAll();
    setAccessToken(null);
    dispatch({ type: 'SIGN_OUT' });
  };

  const restoreSession = ({ user, isNewUser, accessToken }) => {
    setAccessToken(accessToken);
    dispatch({
      type: 'RESTORE_SESSION',
      payload: { user, isNewUser, accessToken },
    });
  };

  const finishLoading = () => {
    dispatch({ type: 'LOADING_COMPLETE' });
  };

  return (
    <AuthContext.Provider
      value={{
        ...state,
        signIn,
        signOut,
        restoreSession,
        finishLoading,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
