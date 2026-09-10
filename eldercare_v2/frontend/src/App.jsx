import React, { useState, useEffect } from 'react';
import {
  Routes,
  Route,
  Link,
  useLocation,
  useNavigate,
  Navigate,
} from 'react-router-dom';
import { Menu, X, LogOut, Bell } from 'lucide-react';
import toast, { Toaster } from 'react-hot-toast';

// Pages
import Dashboard from './pages/Dashboard';
import PatientManager from './pages/PatientManager';
import VideoAnalysis from './pages/VideoAnalysis';
import LiveCamera from './pages/LiveCamera';
import PatientDetail from './pages/PatientDetail';
import Timeline from './pages/Timeline';
import SOSAlerts from './pages/SOSAlerts';
import AdminPanel from './pages/AdminPanel';
import Login from './pages/Login';
import Demo from './pages/Demo';
import Settings from './pages/Settings';
import { signOutFirebaseWeb } from './firebase';

// Styles
import './App.css';

const API_BASE = 'http://localhost:8000/api';

function App() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [user, setUser] = useState(null);
  const [unreadAlerts, setUnreadAlerts] = useState(0);
  const [loading, setLoading] = useState(true);

  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    const token = localStorage.getItem('token');

    if (token) {
      loadUser();
    } else {
      setLoading(false);
    }
  }, []);

  const loadUser = async () => {
    try {
      const token = localStorage.getItem('token');
      const authProvider = localStorage.getItem('auth_provider');

      if (!token) {
        setUser(null);
        setLoading(false);
        return;
      }

      const endpoint =
        authProvider === 'firebase' ? `${API_BASE}/auth/firebase/me` : `${API_BASE}/auth/me`;

      const response = await fetch(endpoint, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const userData = await response.json();
        setUser(userData);

        const alertsResponse = await fetch(`${API_BASE}/notifications/unread`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (alertsResponse.ok) {
          const alerts = await alertsResponse.json();
          setUnreadAlerts(alerts.count || 0);
        }

        if (location.pathname === '/login') {
          navigate('/');
        }
      } else {
        localStorage.removeItem('token');
        setUser(null);

        if (location.pathname !== '/login') {
          navigate('/login');
        }
      }
    } catch (error) {
      console.error('Failed to load user:', error);
      localStorage.removeItem('token');
      setUser(null);

      if (location.pathname !== '/login') {
        navigate('/login');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    signOutFirebaseWeb().catch(() => {});
    localStorage.removeItem('token');
    setUser(null);
    setUnreadAlerts(0);
    localStorage.removeItem('auth_provider');
    navigate('/login');
    toast.success('Logged out successfully');
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900 text-white">
        <div className="text-lg font-semibold">Loading ElderCare AI...</div>
      </div>
    );
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={
          user ? (
            <Navigate to="/" replace />
          ) : (
            <Login
              onLoginSuccess={async () => {
                await loadUser();
              }}
            />
          )
        }
      />

      <Route
        path="/*"
        element={
          user ? (
            <AppLayout
              user={user}
              unreadAlerts={unreadAlerts}
              isMenuOpen={isMenuOpen}
              setIsMenuOpen={setIsMenuOpen}
              handleLogout={handleLogout}
              setUnreadAlerts={setUnreadAlerts}
            />
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />
    </Routes>
  );
}

function AppLayout({
  user,
  unreadAlerts,
  isMenuOpen,
  setIsMenuOpen,
  handleLogout,
  setUnreadAlerts,
}) {
  const location = useLocation();

  return (
    <div className="flex h-screen bg-gray-900">
      <Toaster position="top-right" />

      {/* Sidebar Navigation */}
      <nav className="hidden md:block w-64 bg-gray-800 border-r border-gray-700 shadow-lg overflow-y-auto">
        <div className="p-6 border-b border-gray-700">
          <Link to="/" className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold">EC</span>
            </div>
            <div>
              <h1 className="text-white font-bold text-lg">ElderCare</h1>
              <p className="text-gray-400 text-xs">AI Healthcare</p>
            </div>
          </Link>
        </div>

        <div className="p-4">
          <div className="mb-2 text-xs font-semibold text-gray-400 uppercase px-4">
            User
          </div>

          {user && (
            <div className="bg-gray-700 rounded-lg p-3 mb-4">
              <p className="text-white font-semibold text-sm">{user.full_name}</p>
              <p className="text-gray-300 text-xs">{user.role}</p>
            </div>
          )}

          <div className="mb-2 text-xs font-semibold text-gray-400 uppercase px-4 mt-6">
            Menu
          </div>

          <SidebarLink to="/" icon="🏠" label="Dashboard" />
          <SidebarLink to="/patients" icon="👥" label="Patients" />
          <SidebarLink to="/video-analysis" icon="📹" label="Upload Video" />
          <SidebarLink to="/live-camera" icon="📷" label="Live Camera" />
          <SidebarLink to="/timeline" icon="📊" label="Timeline" />
          <SidebarLink
            to="/sos-alerts"
            icon="🚨"
            label="SOS Alerts"
            badge={unreadAlerts}
          />

          {user?.role === 'admin' && (
            <>
              <div className="mb-2 text-xs font-semibold text-gray-400 uppercase px-4 mt-6">
                Admin
              </div>
              <SidebarLink to="/admin" icon="⚙️" label="Admin Panel" />
              <SidebarLink to="/demo" icon="🎬" label="Demo Mode" />
            </>
          )}

          <div className="mb-2 text-xs font-semibold text-gray-400 uppercase px-4 mt-6">
            Account
          </div>

          <SidebarLink to="/settings" icon="⚙️" label="Settings" />

          <button
            onClick={handleLogout}
            className="w-full text-left px-4 py-2 text-gray-300 hover:bg-gray-700 hover:text-white rounded-lg flex items-center gap-3 transition-colors"
          >
            <LogOut size={18} />
            Logout
          </button>
        </div>
      </nav>

      {/* Mobile Menu Button */}
      <div className="md:hidden fixed top-4 left-4 z-50">
        <button
          onClick={() => setIsMenuOpen(!isMenuOpen)}
          className="bg-gray-800 p-2 rounded-lg text-white"
        >
          {isMenuOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {/* Mobile Menu */}
      {isMenuOpen && (
        <div className="md:hidden fixed inset-0 bg-gray-800 z-40 pt-16">
          <nav className="p-4 space-y-2">
            <SidebarLink
              to="/"
              icon="🏠"
              label="Dashboard"
              mobile
              onClick={() => setIsMenuOpen(false)}
            />
            <SidebarLink
              to="/patients"
              icon="👥"
              label="Patients"
              mobile
              onClick={() => setIsMenuOpen(false)}
            />
            <SidebarLink
              to="/video-analysis"
              icon="📹"
              label="Upload Video"
              mobile
              onClick={() => setIsMenuOpen(false)}
            />
            <SidebarLink
              to="/live-camera"
              icon="📷"
              label="Live Camera"
              mobile
              onClick={() => setIsMenuOpen(false)}
            />
            <SidebarLink
              to="/timeline"
              icon="📊"
              label="Timeline"
              mobile
              onClick={() => setIsMenuOpen(false)}
            />
            <SidebarLink
              to="/sos-alerts"
              icon="🚨"
              label="SOS Alerts"
              mobile
              badge={unreadAlerts}
              onClick={() => setIsMenuOpen(false)}
            />

            {user?.role === 'admin' && (
              <>
                <SidebarLink
                  to="/admin"
                  icon="⚙️"
                  label="Admin Panel"
                  mobile
                  onClick={() => setIsMenuOpen(false)}
                />
                <SidebarLink
                  to="/demo"
                  icon="🎬"
                  label="Demo Mode"
                  mobile
                  onClick={() => setIsMenuOpen(false)}
                />
              </>
            )}

            <SidebarLink
              to="/settings"
              icon="⚙️"
              label="Settings"
              mobile
              onClick={() => setIsMenuOpen(false)}
            />

            <button
              onClick={() => {
                setIsMenuOpen(false);
                handleLogout();
              }}
              className="w-full text-left px-4 py-2 text-gray-300 hover:bg-gray-700 rounded-lg flex items-center gap-3"
            >
              <LogOut size={18} />
              Logout
            </button>
          </nav>
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Bar */}
        <header className="bg-gray-800 border-b border-gray-700 px-6 py-4 flex items-center justify-between">
          <h2 className="text-white text-xl font-semibold">
            {getPageTitle(location.pathname)}
          </h2>

          <div className="flex items-center gap-4">
            <button className="relative p-2 text-gray-300 hover:text-white">
              <Bell size={20} />
              {unreadAlerts > 0 && (
                <span className="absolute top-0 right-0 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
                  {unreadAlerts}
                </span>
              )}
            </button>

            <div className="h-8 w-8 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-lg" />
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-auto bg-gray-900">
          <Routes>
            <Route path="/" element={<Dashboard API_BASE={API_BASE} />} />
            <Route path="/patients" element={<PatientManager API_BASE={API_BASE} />} />
            <Route path="/patients/:id" element={<PatientDetail API_BASE={API_BASE} />} />
            <Route
              path="/video-analysis"
              element={<VideoAnalysis API_BASE={API_BASE} />}
            />
            <Route path="/live-camera" element={<LiveCamera API_BASE={API_BASE} />} />
            <Route path="/timeline" element={<Timeline API_BASE={API_BASE} />} />
            <Route
              path="/sos-alerts"
              element={
                <SOSAlerts
                  API_BASE={API_BASE}
                  onAlertsRead={() => setUnreadAlerts(0)}
                />
              }
            />
            <Route path="/settings" element={<Settings API_BASE={API_BASE} />} />

            {user?.role === 'admin' && (
              <>
                <Route path="/admin" element={<AdminPanel API_BASE={API_BASE} />} />
                <Route path="/demo" element={<Demo API_BASE={API_BASE} />} />
              </>
            )}

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

function SidebarLink({ to, icon, label, badge, onClick }) {
  const location = useLocation();
  const isActive = location.pathname === to;

  return (
    <Link
      to={to}
      onClick={onClick}
      className={`block px-4 py-2 rounded-lg transition-colors flex items-center gap-3 ${
        isActive
          ? 'bg-blue-600 text-white'
          : 'text-gray-300 hover:bg-gray-700 hover:text-white'
      }`}
    >
      <span>{icon}</span>
      <span>{label}</span>
      {badge > 0 && (
        <span className="ml-auto bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
          {badge}
        </span>
      )}
    </Link>
  );
}

function getPageTitle(pathname) {
  if (pathname.startsWith('/patients/')) return 'Patient Details';

  const titles = {
    '/': 'Dashboard',
    '/patients': 'Patient Management',
    '/video-analysis': 'Video Upload & Analysis',
    '/live-camera': 'Live Camera Detection',
    '/timeline': 'Activity Timeline',
    '/sos-alerts': 'SOS Alerts',
    '/settings': 'Settings',
    '/admin': 'Admin Panel',
    '/demo': 'Demo Mode',
  };

  return titles[pathname] || 'ElderCare';
}

export default App;
