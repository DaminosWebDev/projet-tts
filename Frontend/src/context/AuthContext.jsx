// context/AuthContext.jsx
// État global d'authentification — accessible dans toute l'app via useAuth()
// Gère : tokens JWT, user courant, refresh automatique, persistance localStorage

import { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import {
  apiLogin, apiRegister, apiRefreshToken,
  apiGetMe, apiGoogleLogin,
} from '../services/api';

const AuthContext = createContext(null);

// Clés localStorage
const KEYS = {
  access:  'vb_access_token',
  refresh: 'vb_refresh_token',
};

// Décode le payload JWT sans vérification (lecture seule côté client)
const decodeJwt = (token) => {
  try {
    return JSON.parse(atob(token.split('.')[1]));
  } catch {
    return null;
  }
};

// Retourne le nombre de ms avant expiration du token (0 si expiré)
const msUntilExpiry = (token) => {
  const payload = decodeJwt(token);
  if (!payload?.exp) return 0;
  return Math.max(0, payload.exp * 1000 - Date.now());
};

export function AuthProvider({ children }) {
  const [user, setUser]         = useState(null);
  const [accessToken, setAccessToken] = useState(() => localStorage.getItem(KEYS.access));
  const [refreshToken, setRefreshToken] = useState(() => localStorage.getItem(KEYS.refresh));
  const [loading, setLoading]   = useState(true); // true pendant la vérification initiale
  const refreshTimerRef = useRef(null);

  // Persiste les tokens et programme le refresh automatique
  const saveTokens = useCallback((access, refresh) => {
    localStorage.setItem(KEYS.access, access);
    localStorage.setItem(KEYS.refresh, refresh);
    setAccessToken(access);
    setRefreshToken(refresh);
    scheduleRefresh(access, refresh);
  }, []);

  const clearTokens = useCallback(() => {
    localStorage.removeItem(KEYS.access);
    localStorage.removeItem(KEYS.refresh);
    setAccessToken(null);
    setRefreshToken(null);
    setUser(null);
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
  }, []);

  // Refresh silencieux — appelé automatiquement 1 minute avant expiration
  const doRefresh = useCallback(async (currentRefresh) => {
    if (!currentRefresh) return;
    try {
      const tokens = await apiRefreshToken(currentRefresh);
      saveTokens(tokens.access_token, tokens.refresh_token);
    } catch {
      // Refresh token expiré — déconnexion forcée
      clearTokens();
    }
  }, [saveTokens, clearTokens]);

  const scheduleRefresh = useCallback((access, refresh) => {
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    const ms = msUntilExpiry(access) - 60_000; // 1 minute avant expiration
    if (ms > 0) {
      refreshTimerRef.current = setTimeout(() => doRefresh(refresh), ms);
    }
  }, [doRefresh]);

  // Au montage — vérifie si les tokens stockés sont encore valides
  useEffect(() => {
    const init = async () => {
      const access  = localStorage.getItem(KEYS.access);
      const refresh = localStorage.getItem(KEYS.refresh);

      if (!access || !refresh) {
        setLoading(false);
        return;
      }

      // Token encore valide — récupère le profil
      if (msUntilExpiry(access) > 0) {
        try {
          const me = await apiGetMe(access);
          setUser(me);
          scheduleRefresh(access, refresh);
        } catch {
          // Token invalide malgré la date — nettoie
          clearTokens();
        }
      } else {
        // Token expiré — tente un refresh immédiat
        await doRefresh(refresh);
      }

      setLoading(false);
    };

    init();

    return () => {
      if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    };
  }, []);

  // Quand le token change, recharge le profil
  useEffect(() => {
    if (!accessToken) return;
    apiGetMe(accessToken)
      .then(setUser)
      .catch(() => {});
  }, [accessToken]);

  // ── Actions publiques ─────────────────────────────────────────────────────

  const login = async ({ email, password }) => {
    const tokens = await apiLogin({ email, password });
    saveTokens(tokens.access_token, tokens.refresh_token);
    // Le useEffect sur accessToken rechargera le profil automatiquement
  };

  const register = async ({ email, password }) => {
    // register ne retourne pas de tokens — l'user doit vérifier son email
    return apiRegister({ email, password });
  };

  const logout = () => {
    clearTokens();
  };

  const loginWithGoogle = () => {
    apiGoogleLogin(); // Redirige vers le backend
  };

  // Appelé depuis la page /auth/callback après redirection Google
  // Le backend redirige vers le frontend avec les tokens en query params
  const handleOAuthCallback = (access, refresh) => {
    saveTokens(access, refresh);
  };

  return (
    <AuthContext.Provider value={{
      user,
      accessToken,
      loading,
      isAuthenticated: !!user,
      login,
      register,
      logout,
      loginWithGoogle,
      handleOAuthCallback,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

// Hook d'accès au contexte
export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth doit être utilisé dans AuthProvider');
  return ctx;
};
