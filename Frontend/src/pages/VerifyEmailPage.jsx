// pages/VerifyEmailPage.jsx
// Appelée quand l'utilisateur clique sur le lien dans l'email de vérification
// URL : /verify-email?token=xxx
import { useEffect, useState } from 'react';
import { apiVerifyEmail } from '../services/api';
import { useAuth } from '../context/AuthContext';
import '../components/Auth/Auth.css';

export default function VerifyEmailPage({ onNavigate }) {
  const { handleOAuthCallback } = useAuth();
  const [status, setStatus] = useState('loading'); // loading | success | error
  const [message, setMessage] = useState('');

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');

    if (!token) {
      setStatus('error');
      setMessage('Token manquant dans l\'URL.');
      return;
    }

    apiVerifyEmail(token)
      .then((tokens) => {
        // Le backend connecte automatiquement l'user après vérification
        handleOAuthCallback(tokens.access_token, tokens.refresh_token);
        setStatus('success');
        // Redirige vers l'app principale après 2s
        setTimeout(() => onNavigate('home'), 2000);
      })
      .catch((err) => {
        setStatus('error');
        setMessage(err.message || 'Token invalide ou déjà utilisé.');
      });
  }, []);

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-card-top" />
        <div className="auth-logo">
          <div className="auth-logo-dot" />
          <span className="auth-logo-name">VoxBridge</span>
        </div>

        {status === 'loading' && (
          <div style={{ textAlign: 'center', padding: '32px 0' }}>
            <div className="spinner" style={{ width: '32px', height: '32px', borderWidth: '3px', margin: '0 auto 16px', borderColor: 'rgba(79,142,255,0.2)', borderTopColor: 'var(--accent-blue)' }} />
            <p style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--text-secondary)', letterSpacing: '1px' }}>
              Vérification en cours...
            </p>
          </div>
        )}

        {status === 'success' && (
          <div style={{ textAlign: 'center', padding: '20px 0' }}>
            <div style={{ fontSize: '40px', marginBottom: '16px' }}>🎉</div>
            <h2 className="auth-title" style={{ marginBottom: '12px' }}>Email vérifié !</h2>
            <div className="auth-success">
              Votre compte est actif. Redirection en cours...
            </div>
          </div>
        )}

        {status === 'error' && (
          <div style={{ textAlign: 'center', padding: '20px 0' }}>
            <div style={{ fontSize: '40px', marginBottom: '16px' }}>❌</div>
            <h2 className="auth-title" style={{ marginBottom: '12px' }}>Lien invalide</h2>
            <div className="auth-error" style={{ textAlign: 'left' }}>
              <span>⚠</span> {message}
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
