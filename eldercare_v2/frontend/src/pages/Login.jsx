import React, { useState } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { isFirebaseWebAuthConfigured, signInWithGooglePopup } from '../firebase';

const Login = ({ onLoginSuccess }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const response = await axios.post('http://localhost:8000/api/auth/login', {
        email,
        password
      });
      if (response.data.success) {
        localStorage.setItem('token', response.data.token);
        localStorage.setItem('user_id', response.data.user_id);
        localStorage.setItem('role', response.data.role);
        toast.success('Login successful');
        onLoginSuccess?.();
      } else {
        toast.error(response.data.message || 'Login failed');
      }
    } catch (error) {
      toast.error(error.response?.data?.message || 'Invalid credentials');
    }
    setLoading(false);
  };

  const handleGoogleLogin = async () => {
    setGoogleLoading(true);
    try {
      const { idToken } = await signInWithGooglePopup();
      const response = await axios.post('http://localhost:8000/api/auth/firebase', {
        id_token: idToken,
        role: 'caretaker',
      });

      if (response.data.success) {
        localStorage.setItem('token', response.data.token);
        localStorage.setItem('user_id', response.data.user_id);
        localStorage.setItem('role', response.data.role);
        localStorage.setItem('auth_provider', 'firebase');
        toast.success('Google sign-in successful');
        onLoginSuccess?.();
      } else {
        toast.error(response.data.message || 'Google sign-in failed');
      }
    } catch (error) {
      console.error('Google auth failed:', error?.response?.data || error);
      toast.error(error?.response?.data?.detail || error.message || 'Google sign-in failed');
    } finally {
      setGoogleLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 to-gray-800 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-8">
          <div className="text-center mb-8">
            <h1 className="text-white text-3xl font-bold">ElderCare AI</h1>
            <p className="text-gray-400 text-sm mt-2">Professional Healthcare Monitoring</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-gray-300 text-sm font-semibold mb-2">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@eldercare.com"
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                required
              />
            </div>
            <div>
              <label className="block text-gray-300 text-sm font-semibold mb-2">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                required
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white py-2 rounded-lg font-semibold transition-colors"
            >
              {loading ? 'Logging in...' : 'Login'}
            </button>
          </form>

          <div className="mt-4 mb-4 flex items-center gap-3">
            <div className="h-px flex-1 bg-gray-700" />
            <span className="text-gray-400 text-xs uppercase tracking-wide">or</span>
            <div className="h-px flex-1 bg-gray-700" />
          </div>

          <button
            type="button"
            onClick={handleGoogleLogin}
            disabled={googleLoading || !isFirebaseWebAuthConfigured}
            className="w-full bg-white hover:bg-gray-100 disabled:bg-gray-500 disabled:text-gray-200 text-gray-900 py-2 rounded-lg font-semibold transition-colors"
          >
            {googleLoading ? 'Connecting to Google...' : 'Continue with Google'}
          </button>

          {!isFirebaseWebAuthConfigured && (
            <p className="text-yellow-400 text-xs text-center mt-3">
              Google sign-in needs Firebase web config in the frontend environment first.
            </p>
          )}

          <p className="text-gray-400 text-xs text-center mt-6">
            Demo credentials: admin@eldercare.com / password123
          </p>
        </div>
      </div>
    </div>
  );
};

export default Login;
