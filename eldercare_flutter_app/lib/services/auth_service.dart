import 'package:firebase_auth/firebase_auth.dart';
import 'package:google_sign_in/google_sign_in.dart';

/// Service for Firebase Authentication
class AuthService {
  static final FirebaseAuth _auth = FirebaseAuth.instance;
  static final GoogleSignIn _googleSignIn = GoogleSignIn(
    scopes: const ['email'],
  );

  /// Disable reCAPTCHA for development/testing
  static Future<void> disableRecaptchaForTesting() async {
    _auth.setSettings(
      appVerificationDisabledForTesting: true,
    );
  }

  /// Get current authenticated user
  User? get currentUser => _auth.currentUser;

  /// Stream of authentication state changes
  Stream<User?> get authStateChanges => _auth.authStateChanges();

  /// Check if user is authenticated
  bool get isAuthenticated => _auth.currentUser != null;

  /// Sign up with email and password
  /// Returns uid on success, throws exception on failure
  Future<String> signup({
    required String email,
    required String password,
    required String name,
  }) async {
    try {
      final userCredential = await _auth.createUserWithEmailAndPassword(
        email: email,
        password: password,
      );

      // Update display name
      await userCredential.user?.updateDisplayName(name);
      await userCredential.user?.reload();

      return userCredential.user!.uid;
    } on FirebaseAuthException catch (e) {
      throw _handleAuthError(e);
    } catch (e) {
      throw 'Signup failed: $e';
    }
  }

  /// Login with email and password
  /// Returns uid on success, throws exception on failure
  Future<String> login({
    required String email,
    required String password,
  }) async {
    try {
      final userCredential = await _auth.signInWithEmailAndPassword(
        email: email,
        password: password,
      );

      return userCredential.user!.uid;
    } on FirebaseAuthException catch (e) {
      throw _handleAuthError(e);
    } catch (e) {
      throw 'Login failed: $e';
    }
  }

  /// Login with Google account
  Future<String> signInWithGoogle() async {
    try {
      final googleUser = await _googleSignIn.signInSilently() ??
          await _googleSignIn.signIn();
      if (googleUser == null) {
        throw 'Google sign-in was cancelled.';
      }

      final googleAuth = await googleUser.authentication;
      final credential = GoogleAuthProvider.credential(
        accessToken: googleAuth.accessToken,
        idToken: googleAuth.idToken,
      );

      final userCredential = await _auth.signInWithCredential(credential);
      return userCredential.user!.uid;
    } on FirebaseAuthException catch (e) {
      throw _handleAuthError(e);
    } catch (e) {
      throw 'Google sign-in failed: $e';
    }
  }

  /// Get Firebase ID token for backend-authenticated requests
  Future<String?> getIdToken({bool forceRefresh = false}) async {
    return _auth.currentUser?.getIdToken(forceRefresh);
  }

  /// Logout current user
  Future<void> logout() async {
    try {
      await _googleSignIn.signOut();
      await _auth.signOut();
    } catch (e) {
      throw 'Logout failed: $e';
    }
  }

  /// Send password reset email
  Future<void> sendPasswordReset(String email) async {
    try {
      await _auth.sendPasswordResetEmail(email: email);
    } on FirebaseAuthException catch (e) {
      throw _handleAuthError(e);
    } catch (e) {
      throw 'Failed to send reset email: $e';
    }
  }

  /// Update user password
  Future<void> updatePassword({required String newPassword}) async {
    try {
      await _auth.currentUser?.updatePassword(newPassword);
    } on FirebaseAuthException catch (e) {
      throw _handleAuthError(e);
    } catch (e) {
      throw 'Failed to update password: $e';
    }
  }

  /// Delete user account
  Future<void> deleteAccount() async {
    try {
      await _auth.currentUser?.delete();
    } on FirebaseAuthException catch (e) {
      throw _handleAuthError(e);
    } catch (e) {
      throw 'Failed to delete account: $e';
    }
  }

  /// Handle Firebase Auth errors
  String _handleAuthError(FirebaseAuthException e) {
    switch (e.code) {
      case 'weak-password':
        return 'Password is too weak. Use at least 6 characters.';
      case 'email-already-in-use':
        return 'Email is already registered. Try logging in.';
      case 'invalid-email':
        return 'Invalid email address.';
      case 'operation-not-allowed':
        return 'Email/password authentication is not enabled.';
      case 'user-disabled':
        return 'User account has been disabled.';
      case 'user-not-found':
        return 'User not found. Check your email.';
      case 'wrong-password':
        return 'Wrong password. Try again.';
      case 'too-many-requests':
        return 'Too many failed login attempts. Try again later.';
      case 'account-exists-with-different-credential':
        return 'Account exists with different credentials.';
      case 'invalid-credential':
        return 'Invalid credentials provided.';
      default:
        return 'Authentication error: ${e.message}';
    }
  }
}
