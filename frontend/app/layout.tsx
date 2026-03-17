import './globals.css';
import Link from 'next/link';

function Icon({ path }: { path: string }) {
  return (
    <svg className="nav-icon" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d={path} stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

const nav = [
  ['/dashboard', 'Dashboard', <Icon key="d" path="M3 12h8V3H3v9Zm10 9h8v-6h-8v6Zm0-8h8V3h-8v10Zm-10 8h8v-6H3v6Z" />],
  ['/reservations', 'Reservations', <Icon key="r" path="M5 4h14v16H5z M8 2v4 M16 2v4 M5 9h14" />],
  ['/clients', 'Clients', <Icon key="c" path="M16 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2 M18 7a4 4 0 1 1 0 8 M11 7a4 4 0 1 1 0 8" />],
  ['/calls', 'Calls Live', <Icon key="p" path="M22 16.92v3a2 2 0 0 1-2.18 2 19.86 19.86 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.86 19.86 0 0 1 2.12 4.2 2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.12.89.32 1.77.59 2.62a2 2 0 0 1-.45 2.11L8 10a16 16 0 0 0 6 6l1.55-1.25a2 2 0 0 1 2.11-.45c.85.27 1.73.47 2.62.59A2 2 0 0 1 22 16.92Z" />],
  ['/transcripts', 'Transcripts Live', <Icon key="t" path="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />],
  ['/agent', 'Agent', <Icon key="a" path="M12 2v4 M5 10h14 M7 10v6a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2v-6 M9 14h.01 M15 14h.01" />],
  ['/inventory', 'Inventaire', <Icon key="i" path="M3 7 12 3l9 4-9 4-9-4Zm0 5 9 4 9-4 M3 17l9 4 9-4" />],
  ['/settings', 'Settings', <Icon key="s" path="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Zm8.94 4a6.97 6.97 0 0 0-.12-1l2.03-1.58-2-3.46-2.48 1a8.46 8.46 0 0 0-1.73-1L16.3 2h-4.6l-.34 2.96a8.46 8.46 0 0 0-1.73 1l-2.48-1-2 3.46L7.18 11a6.97 6.97 0 0 0 0 2l-2.03 1.58 2 3.46 2.48-1a8.46 8.46 0 0 0 1.73 1L11.7 22h4.6l.34-2.96a8.46 8.46 0 0 0 1.73-1l2.48 1 2-3.46L20.82 13c.07-.33.12-.66.12-1Z" />],
] as const;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body>
        <div className="app-shell">
          <aside className="sidebar">
            <div className="brand-wrap">
              <img src="/assets/images/guestflow-logo.svg" alt="GuestFlow" className="brand-logo" />
              <div>
                <div className="brand">GuestFlow Admin</div>
                <div className="small">Multi-tenant live suite</div>
              </div>
            </div>
            <nav className="nav-list">
              {nav.map(([href, label, icon]) => (
                <Link className="nav-item" key={href} href={href}>
                  {icon}
                  <span>{label}</span>
                </Link>
              ))}
            </nav>
          </aside>
          <main className="main">{children}</main>
        </div>
      </body>
    </html>
  );
}
