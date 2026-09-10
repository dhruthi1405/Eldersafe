import 'dart:convert';

import 'package:http/http.dart' as http;

import 'auth_service.dart';

/// Connects the Flutter app to the ElderCare backend for monitoring data.
class MonitoringApiService {
  MonitoringApiService({AuthService? authService})
      : _authService = authService ?? AuthService();

  final AuthService _authService;

  static const String _defaultBaseUrl = String.fromEnvironment(
    'BACKEND_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );

  String get baseUrl => _defaultBaseUrl;

  Future<String> _requireIdToken() async {
    final token = await _authService.getIdToken(forceRefresh: true);
    if (token == null || token.isEmpty) {
      throw 'No Firebase session found. Please log in again.';
    }
    return token;
  }

  Future<void> syncFirebaseUser({String role = 'caretaker'}) async {
    final idToken = await _requireIdToken();
    final response = await http.post(
      Uri.parse('$baseUrl/api/auth/firebase'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'id_token': idToken,
        'role': role,
      }),
    );

    if (response.statusCode >= 400) {
      throw _extractError(response, fallback: 'Failed to sync Firebase user with backend.');
    }
  }

  Future<void> registerDeviceToken({
    required String deviceToken,
    String platform = 'mobile',
  }) async {
    final idToken = await _requireIdToken();
    final response = await http.post(
      Uri.parse('$baseUrl/api/mobile/register-device'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'id_token': idToken,
        'device_token': deviceToken,
        'platform': platform,
      }),
    );

    if (response.statusCode >= 400) {
      throw _extractError(response, fallback: 'Failed to register device for alerts.');
    }
  }

  Future<Map<String, dynamic>> fetchMonitoringSummary() async {
    final idToken = await _requireIdToken();
    final response = await http.get(
      Uri.parse('$baseUrl/api/mobile/monitoring'),
      headers: {
        'Authorization': 'Bearer $idToken',
      },
    );

    if (response.statusCode >= 400) {
      throw _extractError(response, fallback: 'Failed to load monitoring summary.');
    }

    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<void> sendTestEmail(String recipientEmail) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/alerts/test-email'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'recipient_email': recipientEmail}),
    );

    if (response.statusCode >= 400) {
      throw _extractError(response, fallback: 'Failed to send test email.');
    }
  }

  /// Get recent alerts for the current user
  Future<List<Map<String, dynamic>>> getRecentAlerts({int limit = 50}) async {
    try {
      final idToken = await _requireIdToken();
      final response = await http.get(
        Uri.parse('$baseUrl/api/notifications/alerts?limit=$limit'),
        headers: {
          'Authorization': 'Bearer $idToken',
        },
      );

      if (response.statusCode >= 400) {
        throw _extractError(response, fallback: 'Failed to load alerts');
      }

      final data = jsonDecode(response.body) as Map<String, dynamic>;
      final alerts = data['alerts'] as List;
      return alerts.cast<Map<String, dynamic>>();
    } catch (e) {
      print('Error loading alerts: $e');
      return [];
    }
  }

  /// Get incident details by ID
  Future<Map<String, dynamic>> getIncidentDetails({
    required String patientId,
    required String incidentType,
  }) async {
    try {
      final idToken = await _requireIdToken();
      final response = await http.get(
        Uri.parse('$baseUrl/api/notifications/alerts/$patientId'),
        headers: {
          'Authorization': 'Bearer $idToken',
        },
      );

      if (response.statusCode >= 400) {
        throw _extractError(response, fallback: 'Failed to load incident details');
      }

      final data = jsonDecode(response.body) as Map<String, dynamic>;
      return data['incident'] ?? {};
    } catch (e) {
      print('Error loading incident details: $e');
      return {};
    }
  }

  /// Mark incident as resolved
  Future<void> markIncidentResolved(String incidentId) async {
    try {
      final idToken = await _requireIdToken();
      final response = await http.post(
        Uri.parse('$baseUrl/api/notifications/alerts/$incidentId/resolve'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $idToken',
        },
      );

      if (response.statusCode >= 400) {
        throw _extractError(response, fallback: 'Failed to mark as resolved');
      }
    } catch (e) {
      print('Error marking incident as resolved: $e');
      rethrow;
    }
  }

  String _extractError(http.Response response, {required String fallback}) {
    try {
      final payload = jsonDecode(response.body) as Map<String, dynamic>;
      return payload['detail']?.toString() ??
          payload['message']?.toString() ??
          fallback;
    } catch (_) {
      return fallback;
    }
  }
}

