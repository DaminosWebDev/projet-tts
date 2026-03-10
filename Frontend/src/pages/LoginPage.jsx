// pages/LoginPage.jsx
import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import '../components/Auth/Auth.css';

export default function LoginPage({ onNavigate }) {
  const { login, loginWithGoogle } = useAuth();

  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login({ email, password });
      onNavigate('home'); // Retour à l'app principale après connexion
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-card-top" />

        <div className="auth-logo">
          <div className="auth-logo-dot" />
          <span className="auth-logo-name">VoxBridge</span>
        </div>

        <h1 className="auth-title">Connexion</h1>
        <p className="auth-subtitle">Accédez à votre espace vocal</p>

        {error && (
          <div className="auth-error">
            <span>⚠</span> {error}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          <div className="auth-field">
            <label className="auth-label" htmlFor="login-email">Email</label>
            <input
              id="login-email"
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
            <label className="auth-label" htmlFor="login-password">Mot de passe</label>
            <input
              id="login-password"
              type="password"
              className="auth-input"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              autoComplete="current-password"
            />
          </div>

          <div className="auth-forgot">
            <button
              type="button"
              className="auth-link"
              onClick={() => onNavigate('forgot-password')}
            >
              Mot de passe oublié ?
            </button>
          </div>

          <button
            type="submit"
            className="auth-submit"
            disabled={loading || !email || !password}
          >
            {loading ? <><div className="spinner" /> Connexion...</> : 'Se connecter →'}
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
          Pas encore de compte ?{' '}
          <a href="#" onClick={e => { e.preventDefault(); onNavigate('register'); }}>
            Créer un compte
          </a>
        </div>
      </div>
    </div>
  );
}
