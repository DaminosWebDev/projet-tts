// App.jsx — Routeur SPA + AuthProvider
// Pas de react-router — navigation manuelle par état pour rester zero-dépendance

import { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';

import './styles/globals.css';

// Pages
// Pages auth
import LoginPage           from './pages/LoginPage';
import RegisterPage        from './pages/RegisterPage';
import ForgotPasswordPage  from './pages/ForgotPasswordPage';
import ResetPasswordPage   from './pages/ResetPasswordPage';
import VerifyEmailPage     from './pages/VerifyEmailPage';
import OAuthCallbackPage   from './pages/OAuthCallbackPage';

// App principale
import Navbar       from './components/Navbar/Navbar';
import Hero         from './components/Hero/Hero';
import YoutubeSection from './components/YoutubeSection/YoutubeSection';
import VoiceStudio  from './components/VoiceStudio/VoiceStudio';
import Architecture from './components/Architecture/Architecture';

// Composant auth dans la Navbar
import UserMenu from './components/Auth/UserMenu';
import HistoryPanel from './components/History/HistoryPanel';

// ── Détection de la route initiale depuis l'URL ────────────────────────────

const getInitialPage = () => {
  const path = window.location.pathname;
  if (path === '/verify-email')  return 'verify-email';
  if (path === '/reset-password') return 'reset-password';
  if (path === '/auth/callback') return 'auth-callback';
  return 'home';
};

// ── Composant intérieur (a accès au contexte auth) ─────────────────────────

function AppInner() {
  const { isAuthenticated, loading, user } = useAuth();
  const [page, setPage] = useState(getInitialPage);
  const [historyOpen, setHistoryOpen] = useState(false);

  // Synchronise l'URL avec la page courante
  useEffect(() => {
    const paths = {
      'home':            '/',
      'login':           '/login',
      'register':        '/register',
      'forgot-password': '/forgot-password',
      'reset-password':  '/reset-password',
      'verify-email':    '/verify-email',
      'auth-callback':   '/auth/callback',
    };
    const path = paths[page] || '/';
    if (window.location.pathname !== path) {
      window.history.pushState({}, '', path);
    }
  }, [page]);

  // Gère le bouton "retour" du navigateur
  useEffect(() => {
    const handler = () => setPage(getInitialPage());
    window.addEventListener('popstate', handler);
    return () => window.removeEventListener('popstate', handler);
  }, []);

  // Spinner pendant la vérification initiale des tokens
  if (loading) {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--bg-base)',
        flexDirection: 'column',
        gap: '16px',
      }}>
        <div className="spinner" style={{
          width: '32px', height: '32px', borderWidth: '3px',
          borderColor: 'rgba(79,142,255,0.15)',
          borderTopColor: 'var(--accent-blue)',
        }} />
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '11px',
          letterSpacing: '2px',
          color: 'var(--text-muted)',
        }}>
          VOXBRIDGE
        </span>
      </div>
    );
  }

  // ── Pages auth (accessibles à tous) ───────────────────────────────────────

  if (page === 'login')           return <LoginPage          onNavigate={setPage} />;
  if (page === 'register')        return <RegisterPage        onNavigate={setPage} />;
  if (page === 'forgot-password') return <ForgotPasswordPage  onNavigate={setPage} />;
  if (page === 'reset-password')  return <ResetPasswordPage   onNavigate={setPage} />;
  if (page === 'verify-email')    return <VerifyEmailPage     onNavigate={setPage} />;
  if (page === 'auth-callback')   return <OAuthCallbackPage   onNavigate={setPage} />;

  // ── App principale ─────────────────────────────────────────────────────────

  return (
    <>
      <NavbarWithAuth onNavigate={setPage} onOpenHistory={() => setHistoryOpen(true)} />
      <main>
        <Hero />
        <YoutubeSection />
        <VoiceStudio />
        <Architecture />
      </main>
      {historyOpen && (
        <HistoryPanel onClose={() => setHistoryOpen(false)} />
      )}
    </>
  );
}

// ── Navbar enrichie avec auth ──────────────────────────────────────────────

function NavbarWithAuth({ onNavigate, onOpenHistory }) {
  const { isAuthenticated } = useAuth();

  return (
    <Navbar
      authSlot={
        isAuthenticated ? (
          <UserMenu onNavigate={onNavigate} onOpenHistory={onOpenHistory} />
        ) : (
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <button
              onClick={() => onNavigate('login')}
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '11px',
                letterSpacing: '1.5px',
                color: 'var(--text-secondary)',
                background: 'none',
                border: '1px solid var(--border-mid)',
                borderRadius: '3px',
                padding: '7px 14px',
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
              onMouseEnter={e => {
                e.currentTarget.style.borderColor = 'var(--border-accent)';
                e.currentTarget.style.color = 'var(--text-primary)';
              }}
              onMouseLeave={e => {
                e.currentTarget.style.borderColor = 'var(--border-mid)';
                e.currentTarget.style.color = 'var(--text-secondary)';
              }}
            >
              Connexion
            </button>
            <button
              onClick={() => onNavigate('register')}
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '11px',
                letterSpacing: '1.5px',
                color: 'var(--bg-base)',
                background: 'var(--accent-blue)',
                border: '1px solid var(--accent-blue)',
                borderRadius: '3px',
                padding: '7px 14px',
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
              onMouseEnter={e => {
                e.currentTarget.style.boxShadow = '0 4px 16px var(--accent-blue-glow)';
                e.currentTarget.style.transform = 'translateY(-1px)';
              }}
              onMouseLeave={e => {
                e.currentTarget.style.boxShadow = 'none';
                e.currentTarget.style.transform = 'none';
              }}
            >
              S'inscrire
            </button>
          </div>
        )
      }
    />
  );
}

// ── Root export ────────────────────────────────────────────────────────────

export default function App() {
  return (
    <AuthProvider>
      <AppInner />
    </AuthProvider>
  );
}