// pages/ResetPasswordPage.jsx
import { useState, useEffect } from 'react';
import { apiResetPassword } from '../services/api';
import '../components/Auth/Auth.css';

const checkStrength = (password) => {
  const score = [
    password.length >= 8,
    /[A-Z]/.test(password),
    /[a-z]/.test(password),
    /\d/.test(password),
  ].filter(Boolean).length;
  return score;
};

const STRENGTH_CLASSES = ['', 'weak', 'medium', 'strong', 'strong'];
const STRENGTH_LABELS  = ['', 'Faible', 'Moyen', 'Bon', 'Fort'];

export default function ResetPasswordPage({ onNavigate }) {
  const [token, setToken]       = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm]   = useState('');
  const [loading, setLoading]   = useState(false);
  const [success, setSuccess]   = useState('');
  const [error, setError]       = useState('');

  const score = checkStrength(password);
  const confirmError = confirm && password !== confirm
    ? 'Les mots de passe ne correspondent pas'
    : '';

  // Lit le token depuis l'URL ?token=xxx
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const t = params.get('token');
    if (t) setToken(t);
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (score < 4) {
      setError('Le mot de passe ne respecte pas les critères de sécurité.');
      return;
    }

    if (password !== confirm) {
      setError('Les mots de passe ne correspondent pas.');
      return;
    }

    if (!token) {
      setError('Token manquant. Utilisez le lien reçu par email.');
      return;
    }

    setLoading(true);
    try {
      const res = await apiResetPassword({ token, new_password: password });
      setSuccess(res.message);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <div className="auth-card-top" />
          <div className="auth-logo">
            <div className="auth-logo-dot" />
            <span className="auth-logo-name">VoxBridge</span>
          </div>
          <div style={{ textAlign: 'center', padding: '20px 0' }}>
            <div style={{ fontSize: '40px', marginBottom: '16px' }}>✅</div>
            <h2 className="auth-title" style={{ marginBottom: '12px' }}>Mot de passe modifié</h2>
            <div className="auth-success" style={{ textAlign: 'left' }}>{success}</div>
          </div>
          <button
            className="auth-submit"
            onClick={() => onNavigate('login')}
            style={{ marginTop: '8px' }}
          >
            Se connecter →
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-card-top" />

        <div className="auth-logo">
          <div className="auth-logo-dot" />
          <span className="auth-logo-name">VoxBridge</span>
        </div>

        <h1 className="auth-title">Nouveau mot de passe</h1>
        <p className="auth-subtitle">
          Choisissez un mot de passe sécurisé pour votre compte
        </p>

        {!token && (
          <div className="auth-error">
            <span>⚠</span> Token manquant — utilisez le lien reçu par email.
          </div>
        )}

        {error && <div className="auth-error"><span>⚠</span> {error}</div>}

        <form onSubmit={handleSubmit} noValidate>
          <div className="auth-field">
            <label className="auth-label" htmlFor="reset-password">Nouveau mot de passe</label>
            <input
              id="reset-password"
              type="password"
              className={`auth-input${password && score < 4 ? ' error' : ''}`}
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              autoComplete="new-password"
              autoFocus
            />

            {password && (
              <div className="password-strength">
                <div className="strength-bars">
                  {[1,2,3,4].map(i => (
                    <div
                      key={i}
                      className={`strength-bar${score >= i ? ` active-${STRENGTH_CLASSES[score]}` : ''}`}
                    />
                  ))}
                </div>
                <span className={`strength-label ${STRENGTH_CLASSES[score]}`}>
                  {STRENGTH_LABELS[score]}
                </span>
              </div>
            )}
          </div>

          <div className="auth-field">
            <label className="auth-label" htmlFor="reset-confirm">Confirmer</label>
            <input
              id="reset-confirm"
              type="password"
              className={`auth-input${confirmError ? ' error' : ''}`}
              value={confirm}
              onChange={e => setConfirm(e.target.value)}
              placeholder="••••••••"
              required
              autoComplete="new-password"
            />
            {confirmError && <span className="field-error">{confirmError}</span>}
          </div>

          <button
            type="submit"
            className="auth-submit"
            disabled={loading || !token || score < 4 || password !== confirm}
          >
            {loading
              ? <><div className="spinner" /> Modification...</>
              : 'Modifier le mot de passe →'}
          </button>
        </form>
      </div>
    </div>
  );
}
