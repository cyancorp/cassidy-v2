import React, { useState } from 'react';

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
    
    const API_BASE_URL = 'http://localhost:8000/api/v1';
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
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            {isRegistering ? 'Create your account' : 'Sign in to Cassidy'}
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            AI-powered journaling assistant
          </p>
        </div>
        
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          {error && (
            <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}
          
          <div className="rounded-md shadow-sm -space-y-px">
            <div>
              <label htmlFor="username" className="sr-only">Username</label>
              <input
                id="username"
                name="username"
                type="text"
                required
                className="relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-t-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
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
                  className="relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
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
                className={`relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 ${isRegistering ? '' : 'rounded-b-md'} focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm`}
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
              className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
            >
              {isLoading ? 'Processing...' : (isRegistering ? 'Create Account' : 'Sign In')}
            </button>
          </div>

          <div className="text-center">
            <button
              type="button"
              onClick={() => setIsRegistering(!isRegistering)}
              className="text-indigo-600 hover:text-indigo-500 text-sm"
            >
              {isRegistering ? 'Already have an account? Sign in' : 'Need an account? Register'}
            </button>
          </div>

          {!isRegistering && (
            <div className="text-center text-sm text-gray-500">
              <p>Demo credentials:</p>
              <p>Username: <strong>user_123</strong> | Password: <strong>1234</strong></p>
            </div>
          )}
        </form>
      </div>
    </div>
  );
};

export default LoginForm;