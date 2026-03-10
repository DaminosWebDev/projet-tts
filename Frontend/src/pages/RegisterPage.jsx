// pages/RegisterPage.jsx
import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import '../components/Auth/Auth.css';

// Correspond aux règles de is_password_strong() du backend
const checkStrength = (password) => {
  const checks = {
    length:  password.length >= 8,
    upper:   /[A-Z]/.test(password),
    lower:   /[a-z]/.test(password),
    digit:   /\d/.test(password),
  };
  const score = Object.values(checks).filter(Boolean).length;
  return { checks, score };
};

const STRENGTH_LABELS = ['', 'Faible', 'Moyen', 'Bon', 'Fort'];
const STRENGTH_CLASSES = ['', 'weak', 'medium', 'strong', 'strong'];

export default function RegisterPage({ onNavigate }) {
  const { register, loginWithGoogle } = useAuth();

  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm]   = useState('');
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');
  const [success, setSuccess]   = useState('');

  const { checks, score } = checkStrength(password);

  const passwordErrors = () => {
    if (!password) return '';
    if (!checks.length)  return 'Au moins 8 caractères requis';
    if (!checks.upper)   return 'Au moins une majuscule requise';
    if (!checks.lower)   return 'Au moins une minuscule requise';
    if (!checks.digit)   return 'Au moins un chiffre requis';
    return '';
  };

  const confirmError = confirm && password !== confirm
    ? 'Les mots de passe ne correspondent pas'
    : '';

  const canSubmit = email && score === 4 && password === confirm && !loading;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (score < 4) { setError(passwordErrors()); return; }
    if (password !== confirm) { setError('Les mots de passe ne correspondent pas'); return; }

    setLoading(true);
    try {
      const res = await register({ email, password });
      setSuccess(res.message || 'Compte créé ! Vérifiez votre boîte email.');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Après inscription réussie — affiche le message et propose de se connecter
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
            <div style={{ fontSize: '40px', marginBottom: '16px' }}>✉️</div>
            <h2 className="auth-title" style={{ marginBottom: '12px' }}>Vérifiez votre email</h2>
            <p className="auth-subtitle" style={{ marginBottom: '24px' }}>
              Un lien de confirmation a été envoyé à<br />
              <strong style={{ color: 'var(--text-primary)' }}>{email}</strong>
            </p>
            <div className="auth-success">{success}</div>
          </div>

          <div className="auth-footer">
            <a href="#" onClick={e => { e.preventDefault(); onNavigate('login'); }}>
              ← Retour à la connexion
            </a>
          </div>
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

        <h1 className="auth-title">Créer un compte</h1>
        <p className="auth-subtitle">Rejoignez la plateforme vocale</p>

        {error && (
          <div className="auth-error">
            <span>⚠</span> {error}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          <div className="auth-field">
            <label className="auth-label" htmlFor="reg-email">Email</label>
            <input
              id="reg-email"
              type="email"
              className="auth-input"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="vous@exemple.com"
              required
              autoComplete="email"
            />
          </div>

          <div className="auth-field">
            <label className="auth-label" htmlFor="reg-password">Mot de passe</label>
            <input
              id="reg-password"
              type="password"
              className={`auth-input${password && score < 4 ? ' error' : ''}`}
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              autoComplete="new-password"
            />

            {password && (
              <div className="password-strength">
                <div className="strength-bars">
                  {[1, 2, 3, 4].map(i => (
                    <div
                      key={i}
                      className={`strength-bar${score >= i ? ` active-${STRENGTH_CLASSES[score]}` : ''}`}
                    />
                  ))}
                </div>
                <span className={`strength-label ${STRENGTH_CLASSES[score]}`}>
                  {STRENGTH_LABELS[score]}
                  {score < 4 && ` — ${passwordErrors()}`}
                </span>
              </div>
            )}
          </div>

          <div className="auth-field">
            <label className="auth-label" htmlFor="reg-confirm">Confirmer le mot de passe</label>
            <input
              id="reg-confirm"
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
            disabled={!canSubmit}
          >
            {loading
              ? <><div className="spinner" /> Création...</>
              : 'Créer mon compte →'}
          </button>
        </form>

        <div className="auth-divider">
          <div className="auth-divider-line" />
          <span className="auth-divider-text">ou</span>
          <div className="auth-divider-line" />
        </div>

        <button className="auth-google" onClick={loginWithGoogle} type="button">
          <svg width="18" height="18" viewBox="0 0 18 18">
            <path fill="#4285F4" d="M16.51 8H8.98v3h4.3c-.18 1-.74 1.48-1.6 2.04v2.01h2.6a7.8 7.8 0 0 0 2.38-5.88c0-.57-.05-.66-.15-1.18z"/>
            <path fill="#34A853" d="M8.98 17c2.16 0 3.97-.72 5.3-1.94l-2.6-2a4.8 4.8 0 0 1-7.18-2.54H1.83v2.07A8 8 0 0 0 8.98 17z"/>
            <path fill="#FBBC05" d="M4.5 10.52a4.8 4.8 0 0 1 0-3.04V5.41H1.83a8 8 0 0 0 0 7.18l2.67-2.07z"/>
            <path fill="#EA4335" d="M8.98 4.18c1.17 0 2.23.4 3.06 1.2l2.3-2.3A8 8 0 0 0 1.83 5.4L4.5 7.49a4.77 4.77 0 0 1 4.48-3.3z"/>
          </svg>
          Continuer avec Google
        </button>

        <div className="auth-footer">
          Déjà un compte ?{' '}
          <a href="#" onClick={e => { e.preventDefault(); onNavigate('login'); }}>
            Se connecter
          </a>
        </div>
      </div>
    </div>
  );
}
