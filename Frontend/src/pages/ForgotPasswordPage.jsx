// pages/ForgotPasswordPage.jsx
import { useState } from 'react';
import { apiForgotPassword } from '../services/api';
import '../components/Auth/Auth.css';

export default function ForgotPasswordPage({ onNavigate }) {
  const [email, setEmail]     = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState('');
  const [error, setError]     = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await apiForgotPassword({ email });
      // Le backend retourne toujours le même message (anti-énumération)
      setSuccess(res.message);
    } catch (err) {
      // Même en cas d'erreur réseau, on affiche un message neutre
      setSuccess('Si un compte existe avec cet email, vous recevrez un lien.');
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

        <h1 className="auth-title">Mot de passe oublié</h1>
        <p className="auth-subtitle">
          Entrez votre email pour recevoir un lien de réinitialisation
        </p>

        {success ? (
          <>
            <div className="auth-success">{success}</div>
            <p style={{ fontFamily: 'var(--font-body)', fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '20px' }}>
              Vérifiez votre boîte email et vos spams. Le lien est valable 1 heure.
            </p>
          </>
        ) : (
          <>
            {error && <div className="auth-error"><span>⚠</span> {error}</div>}

            <form onSubmit={handleSubmit} noValidate>
              <div className="auth-field">
                <label className="auth-label" htmlFor="forgot-email">Email</label>
                <input
                  id="forgot-email"
                  type="email"
                  className="auth-input"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="vous@exemple.com"
                  required
                  autoFocus
                />
              </div>

              <button
                type="submit"
                className="auth-submit"
                disabled={loading || !email}
              >
                {loading
                  ? <><div className="spinner" /> Envoi...</>
                  : 'Envoyer le lien →'}
              </button>
            </form>
          </>
        )}

        <div className="auth-footer">
          <a href="#" onClick={e => { e.preventDefault(); onNavigate('login'); }}>
            ← Retour à la connexion
          </a>
        </div>
      </div>
    </div>
  );
}
