import './globals.css';
import Link from 'next/link';

function DotIcon() { return <span style={{display:'inline-block', width: 8, height: 8, borderRadius: 99, background:'#4f8cff'}} />; }
function CardIcon() { return <span aria-hidden>??</span>; }
function UserIcon() { return <span aria-hidden>??</span>; }
function PhoneIcon() { return <span aria-hidden>??</span>; }
function FileIcon() { return <span aria-hidden>??</span>; }
function RobotIcon() { return <span aria-hidden>??</span>; }
function GearIcon() { return <span aria-hidden>??</span>; }
function DashIcon() { return <span aria-hidden>??</span>; }

const nav = [
  ['/dashboard', 'Dashboard', <DashIcon key="d" />],
  ['/reservations', 'Reservations', <CardIcon key="r" />],
  ['/clients', 'Clients', <UserIcon key="c" />],
  ['/calls', 'Calls Live', <PhoneIcon key="p" />],
  ['/transcripts', 'Transcripts Live', <FileIcon key="t" />],
  ['/agent', 'Agent', <RobotIcon key="a" />],
  ['/inventory', 'Inventaire', <CardIcon key="i" />],
  ['/settings', 'Settings', <GearIcon key="s" />],
] as const;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body>
        <div className="app-shell">
          <aside className="sidebar">
            <div className="brand" style={{display:'flex', alignItems:'center', gap:10}}><DotIcon />GuestFlow Admin</div>
            {nav.map(([href, label, icon]) => (
              <Link className="nav-item" key={href} href={href}><span style={{marginRight:8}}>{icon}</span>{label}</Link>
            ))}
            <div className="small" style={{marginTop: 16}}>Prototype multi-tenant</div>
          </aside>
          <main className="main">{children}</main>
        </div>
      </body>
    </html>
  );
}
