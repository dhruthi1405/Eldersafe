import { initializeApp, getApps, getApp } from 'firebase/app';
import { getAuth, GoogleAuthProvider, signInWithPopup, signOut } from 'firebase/auth';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || '',
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || '',
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || '',
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || '',
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || '',
  appId: import.meta.env.VITE_FIREBASE_APP_ID || '',
};

const hasFirebaseConfig = Boolean(
  firebaseConfig.apiKey &&
  firebaseConfig.authDomain &&
  firebaseConfig.projectId &&
  firebaseConfig.appId
);

const app = hasFirebaseConfig
  ? (getApps().length ? getApp() : initializeApp(firebaseConfig))
  : null;

const auth = app ? getAuth(app) : null;
const googleProvider = auth ? new GoogleAuthProvider() : null;

export const isFirebaseWebAuthConfigured = hasFirebaseConfig;

export async function signInWithGooglePopup() {
  if (!auth || !googleProvider) {
    throw new Error('Firebase web authentication is not configured yet.');
  }

  const result = await signInWithPopup(auth, googleProvider);
  const idToken = await result.user.getIdToken(true);
  return { result, idToken };
}

export async function signOutFirebaseWeb() {
  if (!auth) return;
  await signOut(auth);
}
