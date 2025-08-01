import Logo from './Logo';
import { useAuth } from '../contexts/AuthContext';

interface HeaderProps {
  currentView: 'chat' | 'journal' | 'tasks';
  onViewChange: (view: 'chat' | 'journal' | 'tasks') => void;
  onNewChat: () => void;
}

export default function Header({ currentView, onViewChange, onNewChat }: HeaderProps) {
  const { username, logout } = useAuth();

  const navItems = [
    { id: 'chat', label: 'Chat', icon: '💬' },
    { id: 'journal', label: 'Journal', icon: '📝' },
    { id: 'tasks', label: 'Tasks', icon: '✓' }
  ] as const;

  return (
    <header className="bg-white border-b border-neutral-200 shadow-soft sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <div className="flex items-center">
            <Logo className="h-8 w-auto text-primary-700" />
          </div>

          {/* Navigation */}
          <nav className="hidden md:flex items-center space-x-1">
            {navItems.map((item) => (
              <button
                key={item.id}
                onClick={() => onViewChange(item.id)}
                className={`
                  px-4 py-2 rounded-lg font-medium text-sm transition-all duration-200
                  ${currentView === item.id
                    ? 'bg-primary-100 text-primary-700'
                    : 'text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100'
                  }
                `}
              >
                <span className="mr-2">{item.icon}</span>
                {item.label}
              </button>
            ))}
          </nav>

          {/* Actions */}
          <div className="flex items-center space-x-4">
            {currentView === 'chat' && (
              <button
                onClick={onNewChat}
                className="hidden sm:flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors font-medium text-sm"
              >
                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                New Chat
              </button>
            )}
            
            <div className="flex items-center space-x-3">
              <span className="text-sm text-neutral-600">
                {username}
              </span>
              <button
                onClick={logout}
                className="text-sm text-neutral-600 hover:text-neutral-900 font-medium"
              >
                Sign out
              </button>
            </div>
          </div>
        </div>

        {/* Mobile navigation */}
        <nav className="md:hidden flex items-center space-x-1 pb-3">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => onViewChange(item.id)}
              className={`
                flex-1 px-3 py-2 rounded-lg font-medium text-sm transition-all duration-200
                ${currentView === item.id
                  ? 'bg-primary-100 text-primary-700'
                  : 'text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100'
                }
              `}
            >
              <span className="mr-1">{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>
      </div>
    </header>
  );
}