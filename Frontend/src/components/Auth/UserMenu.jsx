// components/Auth/UserMenu.jsx
// Avatar + menu déroulant affiché dans la Navbar quand l'user est connecté

import { useState, useRef, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';

export default function UserMenu({ onNavigate, onOpenHistory }) {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const menuRef = useRef(null);

  // Ferme le menu si clic en dehors
  useEffect(() => {
    const handler = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleLogout = () => {
    logout();
    setOpen(false);
  };

  // Initiales pour l'avatar fallback
  const initials = user?.email
    ? user.email.slice(0, 2).toUpperCase()
    : '??';

  return (
    <div ref={menuRef} style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen(o => !o)}
        aria-label="Menu utilisateur"
        aria-expanded={open}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          background: open ? 'var(--accent-blue-dim)' : 'var(--bg-elevated)',
          border: `1px solid ${open ? 'var(--border-accent)' : 'var(--border-mid)'}`,
          borderRadius: '3px',
          padding: '6px 10px',
          cursor: 'pointer',
          transition: 'all 0.2s',
        }}
      >
        {/* Avatar */}
        {user?.avatar_url ? (
          <img
            src={user.avatar_url}
            alt="avatar"
            style={{ width: '22px', height: '22px', borderRadius: '50%', objectFit: 'cover' }}
          />
        ) : (
          <div style={{
            width: '22px', height: '22px', borderRadius: '50%',
            background: 'var(--accent-blue)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: 'var(--font-mono)', fontSize: '9px', fontWeight: 700,
            color: 'var(--bg-base)',
          }}>
            {initials}
          </div>
        )}

        {/* Email tronqué */}
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '11px',
          color: 'var(--text-secondary)',
          maxWidth: '140px',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}>
          {user?.email}
        </span>

        {/* Chevron */}
        <span style={{
          fontSize: '9px',
          color: 'var(--text-muted)',
          transform: open ? 'rotate(180deg)' : 'none',
          transition: 'transform 0.2s',
        }}>▼</span>
      </button>

      {/* Dropdown */}
      {open && (
        <div style={{
          position: 'absolute',
          top: 'calc(100% + 8px)',
          right: 0,
          minWidth: '200px',
          background: 'var(--bg-card)',
          border: '1px solid var(--border-mid)',
          borderRadius: '4px',
          boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
          zIndex: 1000,
          overflow: 'hidden',
          animation: 'fadeUp 0.15s var(--ease-out)',
        }}>
          {/* Infos user */}
          <div style={{
            padding: '12px 16px',
            borderBottom: '1px solid var(--border-subtle)',
          }}>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '10px',
              color: 'var(--text-muted)',
              letterSpacing: '1px',
              marginBottom: '2px',
            }}>
              CONNECTÉ
            </div>
            <div style={{
              fontFamily: 'var(--font-body)',
              fontSize: '13px',
              color: 'var(--text-primary)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}>
              {user?.email}
            </div>
            {!user?.is_verified && (
              <div style={{
                marginTop: '6px',
                fontFamily: 'var(--font-mono)',
                fontSize: '10px',
                color: '#f59e0b',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
              }}>
                ⚠ Email non vérifié
              </div>
            )}
          </div>

          {/* Actions */}
          <div style={{ padding: '6px 0' }}>
            <button
              onClick={() => { setOpen(false); onOpenHistory?.(); }}
              style={{
                width: '100%',
                textAlign: 'left',
                padding: '10px 16px',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                fontFamily: 'var(--font-mono)',
                fontSize: '12px',
                color: 'var(--text-secondary)',
                letterSpacing: '1px',
                transition: 'background 0.15s',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
              onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-elevated)'}
              onMouseLeave={e => e.currentTarget.style.background = 'none'}
            >
              📋 Historique
            </button>
            <button
              onClick={handleLogout}
              style={{
                width: '100%',
                textAlign: 'left',
                padding: '10px 16px',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                fontFamily: 'var(--font-mono)',
                fontSize: '12px',
                color: 'var(--accent-red)',
                letterSpacing: '1px',
                transition: 'background 0.15s',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
              onMouseEnter={e => e.currentTarget.style.background = 'var(--accent-red-dim)'}
              onMouseLeave={e => e.currentTarget.style.background = 'none'}
            >
              ⏻ Déconnexion
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
