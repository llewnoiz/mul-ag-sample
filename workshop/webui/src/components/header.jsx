import { useContext } from 'react';
import { signOut } from 'aws-amplify/auth';
import { CustomerContext } from './contexts.js';
import { useTheme } from './theme-context.jsx';

export const Header = () => {
  const customer = useContext(CustomerContext);
  const { theme, toggleTheme } = useTheme();
  const initials = `${(customer?.first_name || '')[0] || ''}${(customer?.last_name || '')[0] || ''}`;

  return (
    <header id="interface-header" className="sticky top-0 z-50 w-full border-b border-border bg-card shadow-sm">
      <div className="flex h-14 items-center px-6">
        {/* Logo */}
        <div className="flex items-center gap-2 mr-8">
          <div className="h-7 w-7 rounded-md bg-yellow-500 flex items-center justify-center">
            <svg className="h-4 w-4 text-black" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <a href="#/" className="font-semibold text-lg text-foreground no-underline">Electrify! Plus</a>
        </div>

        {/* Nav links */}
        <nav className="flex items-center gap-1 text-sm">
          <a href="#/" className="px-3 py-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary/50 transition-colors no-underline">Dashboard</a>
          <a href="#/usage" className="px-3 py-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary/50 transition-colors no-underline">Usage</a>
          <a href="#/billing" className="px-3 py-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary/50 transition-colors no-underline">Billing</a>
        </nav>

        <div className="ml-auto flex items-center gap-3">
          {/* Theme toggle */}
          <button
            onClick={toggleTheme}
            className="h-9 w-9 rounded-md border border-border flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-secondary/50 transition-colors"
            aria-label="Toggle theme"
          >
            {theme === 'light' ? (
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" /></svg>
            ) : (
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" /></svg>
            )}
          </button>

          {/* User */}
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <div className="h-8 w-8 rounded-full bg-secondary flex items-center justify-center text-xs font-medium text-foreground">{initials}</div>
            <a href="#/account" className="hover:text-foreground transition-colors no-underline text-muted-foreground">
              {customer?.first_name} {customer?.last_name}
            </a>
          </div>

          <button
            onClick={() => signOut()}
            className="text-sm text-muted-foreground hover:text-foreground transition-colors px-3 py-1.5 rounded-md hover:bg-secondary/50 cursor-pointer bg-transparent border-none"
          >
            Sign out
          </button>
        </div>
      </div>
    </header>
  );
};
