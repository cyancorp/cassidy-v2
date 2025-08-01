import React, { useState } from 'react';
import Logo from './Logo';

interface LoginFormProps {
  onLogin: (token: string, username: string) => void;
  isLoading: boolean;
  error: string | null;
}

const LoginForm: React.FC<LoginFormProps> = ({ onLogin, isLoading, error }) => {
  const [username, setUsername] = useState('user_123'); // Default for convenience
  const [password, setPassword] = useState('1234'); // Default for convenience
  const [isRegistering, setIsRegistering] = useState(false);
  const [email, setEmail] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // API URL configuration - same logic as App.tsx
    const API_BASE_URL = (() => {
      // For local development with Vite
      if (import.meta.env.VITE_API_URL) {
        return import.meta.env.VITE_API_URL;
      }
      
      // For deployed version with env-config.js
      if (typeof window !== 'undefined' && (window as any).ENV?.REACT_APP_API_URL) {
        return (window as any).ENV.REACT_APP_API_URL;
      }
      
      // Default to localhost for local development
      if (import.meta.env.DEV) {
        return 'http://localhost:8000/api/v1';
      }
      
      // Fallback for production
      return 'https://tamep5ms5i.execute-api.us-east-1.amazonaws.com/prod/api/v1';
    })();
    const endpoint = isRegistering ? '/auth/register' : '/auth/login';
    
    try {
      const requestBody = isRegistering 
        ? { username, password, email: email || undefined }
        : { username, password };

      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `${isRegistering ? 'Registration' : 'Login'} failed`);
      }

      const data = await response.json();
      
      if (isRegistering) {
        // After successful registration, automatically login
        setIsRegistering(false);
        return;
      }
      
      // Login successful
      onLogin(data.access_token, data.username);
      
    } catch (err: any) {
      console.error(`${isRegistering ? 'Registration' : 'Login'} error:`, err);
      throw err; // Let parent component handle the error
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 to-accent-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8 bg-white p-8 rounded-2xl shadow-large animate-fade-in">
        <div>
          <div className="flex justify-center mb-4">
            <Logo className="h-12 w-auto text-primary-700" />
          </div>
          <h2 className="mt-6 text-center text-3xl font-display font-bold text-neutral-900">
            {isRegistering ? 'Create your account' : 'Welcome to Prism'}
          </h2>
          <p className="mt-2 text-center text-sm text-neutral-600">
            Your AI-powered productivity companion
          </p>
        </div>
        
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          {error && (
            <div className="bg-error/10 border border-error/20 text-error px-4 py-3 rounded-lg text-sm">
              {error}
            </div>
          )}
          
          <div className="space-y-4">
            <div>
              <label htmlFor="username" className="sr-only">Username</label>
              <input
                id="username"
                name="username"
                type="text"
                required
                className="block w-full px-4 py-3 border border-neutral-300 placeholder-neutral-400 text-neutral-900 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all"
                placeholder="Username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </div>
            
            {isRegistering && (
              <div>
                <label htmlFor="email" className="sr-only">Email</label>
                <input
                  id="email"
                  name="email"
                  type="email"
                  className="block w-full px-4 py-3 border border-neutral-300 placeholder-neutral-400 text-neutral-900 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all"
                  placeholder="Email (optional)"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
            )}
            
            <div>
              <label htmlFor="password" className="sr-only">Password</label>
              <input
                id="password"
                name="password"
                type="password"
                required
                className="block w-full px-4 py-3 border border-neutral-300 placeholder-neutral-400 text-neutral-900 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
          </div>

          <div>
            <button
              type="submit"
              disabled={isLoading}
              className="group relative w-full flex justify-center py-3 px-4 border border-transparent text-sm font-medium rounded-xl text-white bg-gradient-primary hover:shadow-glow focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
            >
              {isLoading ? 'Processing...' : (isRegistering ? 'Create Account' : 'Sign In')}
            </button>
          </div>

          <div className="text-center">
            <button
              type="button"
              onClick={() => setIsRegistering(!isRegistering)}
              className="text-primary-600 hover:text-primary-700 text-sm font-medium transition-colors"
            >
              {isRegistering ? 'Already have an account? Sign in' : 'Need an account? Register'}
            </button>
          </div>

          {!isRegistering && (
            <div className="text-center text-sm text-neutral-500 bg-neutral-50 rounded-lg p-3">
              <p className="font-medium mb-1">Demo credentials:</p>
              <p>Username: <strong className="text-neutral-700">user_123</strong> | Password: <strong className="text-neutral-700">1234</strong></p>
            </div>
          )}
        </form>
      </div>
    </div>
  );
};

export default LoginForm;