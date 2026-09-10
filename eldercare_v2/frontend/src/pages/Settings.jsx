import React, { useEffect, useState } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';

const GMAIL_REDIRECT_URI = 'http://localhost:8000/api/settings/gmail/oauth/callback';

const defaultForm = {
  alert_email: '',
  alert_password: '',
  recipient_email: '',
  firebase_key_path: '',
  fcm_device_tokens_file: '',
  gmail_oauth_client_id: '',
  gmail_oauth_client_secret: '',
  gmail_oauth_sender_email: '',
  gmail_oauth_connected: false,
};

const Settings = ({ API_BASE }) => {
  const [form, setForm] = useState(defaultForm);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testingEmail, setTestingEmail] = useState(false);
  const [connectingGmail, setConnectingGmail] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  const authHeaders = () => {
    const token = localStorage.getItem('token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  const loadSettings = async () => {
    try {
      const response = await axios.get(`${API_BASE}/settings`, {
        headers: authHeaders(),
      });
      setForm({
        ...defaultForm,
        ...response.data,
      });
    } catch (error) {
      console.error('Failed to load settings:', error);
      toast.error('Failed to load saved settings');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((current) => ({
      ...current,
      [name]: value,
    }));
  };

  const saveSettings = async () => {
    await axios.put(`${API_BASE}/settings`, form, {
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders(),
      },
    });
  };

  const handleSave = async (event) => {
    event.preventDefault();
    setSaving(true);

    try {
      await saveSettings();
      toast.success('Settings saved');
    } catch (error) {
      console.error('Failed to save settings:', error);
      toast.error(error?.response?.data?.detail || 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const handleTestEmail = async () => {
    if (!form.recipient_email) {
      toast.error('Enter a recipient email first');
      return;
    }

    setTestingEmail(true);
    try {
      await axios.post(
        `${API_BASE}/alerts/test-email`,
        { recipient_email: form.recipient_email },
        {
          headers: {
            'Content-Type': 'application/json',
            ...authHeaders(),
          },
        }
      );
      toast.success('Test email sent');
    } catch (error) {
      console.error('Failed to send test email:', error);
      toast.error(error?.response?.data?.detail || 'Test email failed');
    } finally {
      setTestingEmail(false);
    }
  };

  const handleConnectGmail = async () => {
    if (!form.gmail_oauth_client_id || !form.gmail_oauth_client_secret || !form.gmail_oauth_sender_email) {
      toast.error('Enter Gmail OAuth client id, client secret, and sender email first');
      return;
    }

    setConnectingGmail(true);
    try {
      await saveSettings();
      const response = await axios.post(
        `${API_BASE}/settings/gmail/oauth/start`,
        {
          gmail_oauth_client_id: form.gmail_oauth_client_id,
          gmail_oauth_client_secret: form.gmail_oauth_client_secret,
          gmail_oauth_sender_email: form.gmail_oauth_sender_email,
        },
        {
          headers: {
            'Content-Type': 'application/json',
            ...authHeaders(),
          },
        }
      );

      const authUrl = response?.data?.auth_url;
      if (!authUrl) {
        throw new Error('No Gmail authorization URL returned');
      }

      window.open(authUrl, '_blank', 'noopener,noreferrer');
      toast.success('Google consent screen opened. Finish it, then click Reload Saved Values.');
    } catch (error) {
      console.error('Failed to start Gmail OAuth:', error);
      toast.error(error?.response?.data?.detail || 'Failed to start Gmail OAuth flow');
    } finally {
      setConnectingGmail(false);
    }
  };

  if (loading) {
    return <div className="p-8 text-center text-white">Loading settings...</div>;
  }

  return (
    <div className="p-8">
      <div className="max-w-3xl mx-auto bg-gray-800 border border-gray-700 rounded-xl p-6">
        <h3 className="text-white text-2xl font-semibold mb-2">System Settings</h3>
        <p className="text-gray-400 mb-6">
          Enter your Gmail alert sender, recipient email, and Firebase key path here.
          The website will save them into the backend automatically.
        </p>

        <form className="space-y-5" onSubmit={handleSave}>
          <Field
            label="Alert Email"
            name="alert_email"
            value={form.alert_email}
            onChange={handleChange}
            placeholder="yourgmail@gmail.com"
          />

          <Field
            label="Alert App Password"
            name="alert_password"
            type="password"
            value={form.alert_password}
            onChange={handleChange}
            placeholder="gmail app password"
          />

          <Field
            label="Recipient Email"
            name="recipient_email"
            value={form.recipient_email}
            onChange={handleChange}
            placeholder="caregiver@gmail.com"
          />

          <div className="border border-gray-700 rounded-lg p-4 bg-gray-900/50">
            <h4 className="text-white font-semibold mb-3">Gmail OAuth (Recommended)</h4>
            <p className="text-gray-400 text-sm mb-4">
              Connect once with Google and the backend will store a refresh token for automatic emails.
            </p>

            <div className="mb-4 rounded-lg border border-purple-500/30 bg-purple-500/10 p-3">
              <p className="text-sm font-medium text-purple-200 mb-2">Use this exact Google OAuth redirect URI:</p>
              <code className="block break-all rounded bg-gray-950 px-3 py-2 text-xs text-purple-100">
                {GMAIL_REDIRECT_URI}
              </code>
            </div>

            <div className="space-y-4">
              <Field
                label="Gmail OAuth Client ID"
                name="gmail_oauth_client_id"
                value={form.gmail_oauth_client_id}
                onChange={handleChange}
                placeholder="Google OAuth Client ID"
              />

              <Field
                label="Gmail OAuth Client Secret"
                name="gmail_oauth_client_secret"
                type="password"
                value={form.gmail_oauth_client_secret}
                onChange={handleChange}
                placeholder="Google OAuth Client Secret"
              />

              <Field
                label="Gmail Sender Email"
                name="gmail_oauth_sender_email"
                value={form.gmail_oauth_sender_email}
                onChange={handleChange}
                placeholder="yourgmail@gmail.com"
              />

              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={handleConnectGmail}
                  disabled={connectingGmail}
                  className="px-5 py-2.5 bg-purple-600 hover:bg-purple-500 disabled:opacity-60 text-white rounded-lg font-medium"
                >
                  {connectingGmail ? 'Opening...' : 'Connect Gmail'}
                </button>

                <span className={`text-sm ${form.gmail_oauth_connected ? 'text-emerald-400' : 'text-amber-400'}`}>
                  {form.gmail_oauth_connected ? 'Connected' : 'Not connected'}
                </span>
              </div>
            </div>
          </div>

          <Field
            label="Firebase Service Account Key Path"
            name="firebase_key_path"
            value={form.firebase_key_path}
            onChange={handleChange}
            placeholder="C:/path/to/serviceAccountKey.json"
          />

          <Field
            label="Device Token Store File"
            name="fcm_device_tokens_file"
            value={form.fcm_device_tokens_file}
            onChange={handleChange}
            placeholder="C:/ElderCareProject/runtime/mobile_device_tokens.json"
          />

          <div className="pt-4 flex flex-wrap gap-3">
            <button
              type="submit"
              disabled={saving}
              className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-60 text-white rounded-lg font-medium"
            >
              {saving ? 'Saving...' : 'Save Settings'}
            </button>

            <button
              type="button"
              onClick={handleTestEmail}
              disabled={testingEmail}
              className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-60 text-white rounded-lg font-medium"
            >
              {testingEmail ? 'Sending...' : 'Send Test Email'}
            </button>

            <button
              type="button"
              onClick={loadSettings}
              className="px-5 py-2.5 bg-gray-700 hover:bg-gray-600 text-white rounded-lg font-medium"
            >
              Reload Saved Values
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

function Field({ label, name, value, onChange, placeholder, type = 'text' }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-300 mb-2">{label}</label>
      <input
        type={type}
        name={name}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className="w-full bg-gray-900 border border-gray-600 text-white rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
    </div>
  );
}

export default Settings;
