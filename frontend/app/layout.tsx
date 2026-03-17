import './globals.css';
import Link from 'next/link';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body>
        <nav className="topnav">
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/reservations">Reservations</Link>
          <Link href="/clients">Clients</Link>
          <Link href="/calls">Calls</Link>
          <Link href="/transcripts">Transcripts</Link>
          <Link href="/agent">Agent</Link>
          <Link href="/settings">Settings</Link>
        </nav>
        {children}
      </body>
    </html>
  );
}
