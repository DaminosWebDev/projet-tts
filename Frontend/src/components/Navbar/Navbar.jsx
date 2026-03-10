// components/Navbar/Navbar.jsx
import { useState, useEffect } from 'react';
import './Navbar.css';

const NAV_LINKS = [
  { label: 'Hero',         href: '#hero' },
  { label: 'YouTube',      href: '#youtube' },
  { label: 'Voice Studio', href: '#studio' },
  { label: 'Architecture', href: '#architecture' },
];

export default function Navbar({ authSlot }) {
  const [scrolled, setScrolled]   = useState(false);
  const [active, setActive]       = useState('#hero');
  const [menuOpen, setMenuOpen]   = useState(false);

  useEffect(() => {
    const onScroll = () => {
      setScrolled(window.scrollY > 40);

      // Detect active section
      const sections = ['hero', 'youtube', 'studio', 'architecture'];
      for (let i = sections.length - 1; i >= 0; i--) {
        const el = document.getElementById(sections[i]);
        if (el && window.scrollY >= el.offsetTop - 120) {
          setActive(`#${sections[i]}`);
          break;
        }
      }
    };
    window.addEventListener('scroll', onScroll);
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const handleNav = (href) => {
    setMenuOpen(false);
    const id = href.replace('#', '');
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <>
      <nav className={`navbar${scrolled ? ' scrolled' : ''}`}>
        <div className="nav-logo">
          <div className="nav-logo-dot" />
          VoxBridge
        </div>

        <ul className="nav-links">
          {NAV_LINKS.map(({ label, href }) => (
            <li key={href}>
              <a
                href={href}
                className={active === href ? 'active' : ''}
                onClick={(e) => { e.preventDefault(); handleNav(href); }}
              >
                {label}
              </a>
            </li>
          ))}
        </ul>

        {/* Slot auth — boutons Connexion/Inscription ou UserMenu */}
        {authSlot && (
          <div className="nav-auth-slot">
            {authSlot}
          </div>
        )}

        <button
          className="hamburger"
          onClick={() => setMenuOpen(o => !o)}
          aria-label={menuOpen ? 'Fermer le menu' : 'Ouvrir le menu'}
        >
          <span />
          <span />
          <span />
        </button>
      </nav>

      <div className={`mobile-menu${menuOpen ? ' open' : ''}`}>
        {NAV_LINKS.map(({ label, href }) => (
          <a key={href} href={href} onClick={(e) => { e.preventDefault(); handleNav(href); }}>
            {label}
          </a>
        ))}
      </div>
    </>
  );
}
