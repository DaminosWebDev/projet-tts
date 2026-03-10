// pages/OAuthCallbackPage.jsx
// Page appelée après la redirection Google OAuth
// Le backend redirige vers : FRONTEND_URL/auth/callback?access_token=xxx&refresh_token=xxx
// En cas d'erreur : FRONTEND_URL/auth/callback?error=xxx

import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import '../components/Auth/Auth.css';

export default function OAuthCallbackPage({ onNavigate }) {
  const { handleOAuthCallback } = useAuth();
  const [error, setError] = useState('');

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const accessToken  = params.get('access_token');
    const refreshToken = params.get('refresh_token');
    const err          = params.get('error');

    if (err) {
      setError(decodeURIComponent(err));
      return;
    }

    if (accessToken && refreshToken) {
      handleOAuthCallback(accessToken, refreshToken);
      // Nettoie les tokens de l'URL avant de naviguer
      window.history.replaceState({}, '', window.location.pathname);
      onNavigate('home');
    } else {
      setError('Tokens manquants dans la réponse Google.');
    }
  }, []);

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-card-top" />
        <div className="auth-logo">
          <div className="auth-logo-dot" />
          <span className="auth-logo-name">VoxBridge</span>
        </div>

        {!error ? (
          <div style={{ textAlign: 'center', padding: '32px 0' }}>
            <div className="spinner" style={{
              width: '32px', height: '32px', borderWidth: '3px',
              margin: '0 auto 16px',
              borderColor: 'rgba(79,142,255,0.2)',
              borderTopColor: 'var(--accent-blue)',
            }} />
            <p style={{
              fontFamily: 'var(--font-mono)', fontSize: '12px',
              color: 'var(--text-secondary)', letterSpacing: '1px',
            }}>
              Connexion Google en cours...
            </p>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '20px 0' }}>
            <div style={{ fontSize: '40px', marginBottom: '16px' }}>❌</div>
            <h2 className="auth-title" style={{ marginBottom: '12px' }}>Connexion échouée</h2>
            <div className="auth-error" style={{ textAlign: 'left' }}>
              <span>⚠</span> {error}
            </div>
            <div className="auth-footer" style={{ marginTop: '20px' }}>
              <a href="#" onClick={e => { e.preventDefault(); onNavigate('login'); }}>
                ← Retour à la connexion
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
