import { NavLink, useLocation } from 'react-router'

import { useAuth } from '../auth/AuthContext'
import { BackButton } from './BackButton'

const links = [
  { label: 'Home', to: '/' },
  { label: 'Resumes', to: '/resumes' },
  { label: 'Compose', to: '/outreach' },
  { label: 'Processing', to: '/processing-queue' },
  { label: 'Review', to: '/review-queue' },
  { label: 'Failed tasks', to: '/failed-tasks' },
]

export function AppLayout({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation()
  const { signOut } = useAuth()
  return <div className="app-shell"><header className="app-header"><div className="app-header__inner"><NavLink className="app-brand" to="/">AI Email Agent</NavLink><nav className="app-nav" aria-label="Application navigation">{links.map((link) => <NavLink className="app-nav__link" end={link.to === '/'} key={link.to} to={link.to}>{link.label}</NavLink>)}</nav><button className="button button--secondary app-header__signout" onClick={() => void signOut()} type="button">Sign out</button></div></header>{pathname !== '/' && <div className="back-row"><BackButton /></div>}{children}</div>
}
