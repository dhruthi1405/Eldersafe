import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../screens/incident_details_screen.dart';

class NotificationService {
  static final NotificationService _instance = NotificationService._internal();
  static final FirebaseMessaging _firebaseMessaging = FirebaseMessaging.instance;
  
  static String? _deviceToken;
  static GlobalKey<NavigatorState>? navigatorKey;

  NotificationService._internal();

  factory NotificationService() {
    return _instance;
  }

  /// Initialize Firebase Messaging
  Future<void> initialize({GlobalKey<NavigatorState>? navKey}) async {
    navigatorKey = navKey;
    
    // Request user permission for notifications
    NotificationSettings settings = await _firebaseMessaging.requestPermission(
      alert: true,
      announcement: true,
      badge: true,
      carPlay: false,
      criticalAlert: false,
      provisional: false,
      sound: true,
    );

    print('[FCM] Authorization status: ${settings.authorizationStatus}');

    if (settings.authorizationStatus == AuthorizationStatus.authorized) {
      print('✓ User granted notification permission');
    } else if (settings.authorizationStatus == AuthorizationStatus.provisional) {
      print('⚠ User granted provisional notification permission');
    } else {
      print('✗ User denied notification permission');
      return;
    }

    // Get device token
    try {
      _deviceToken = await _firebaseMessaging.getToken();
      print('📱 Device Token: $_deviceToken');
      
      // Save token locally
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('device_token', _deviceToken ?? '');
      
      // In production, send this token to backend
      // await sendTokenToBackend(_deviceToken);
    } catch (e) {
      print('❌ Failed to get device token: $e');
    }

    // Refresh token when it changes
    _firebaseMessaging.onTokenRefresh.listen((newToken) {
      print('🔄 Device token refreshed: $newToken');
      _deviceToken = newToken;
      _sendTokenToBackend(newToken);
    });

    // Handle foreground messages
    FirebaseMessaging.onMessage.listen((RemoteMessage message) {
      print('📬 Foreground message received');
      _handleForegroundMessage(message);
    });

    // Handle notification tap when app is in background
    FirebaseMessaging.onMessageOpenedApp.listen((RemoteMessage message) {
      print('👆 Background notification tapped');
      _handleMessageTap(message);
    });

    print('✓ Firebase Messaging initialized');
  }

  /// Get current device token
  static String? getDeviceToken() {
    return _deviceToken;
  }

  /// Handle foreground notifications
  void _handleForegroundMessage(RemoteMessage message) {
    print('📬 Foreground message received: ${message.data}');
    
    final notification = message.notification;
    final data = message.data;

    print('Title: ${notification?.title}');
    print('Body: ${notification?.body}');
    print('Data: $data');

    // Show a material dialog to display the notification
    if (navigatorKey?.currentContext != null) {
      _showNotificationDialog(
        context: navigatorKey!.currentContext!,
        title: notification?.title ?? 'Alert',
        body: notification?.body ?? 'New notification',
        data: data,
      );
    }
  }

  /// Handle notification tap
  void _handleMessageTap(RemoteMessage message) {
    print('👆 Notification tapped: ${message.data}');
    
    final alertType = message.data['alert_type'] ?? 'UNKNOWN';
    final patientId = message.data['patient_id'] ?? '';
    final incidentId = message.data['incident_id'] ?? '';
    
    // Navigate based on alert type
    if (navigatorKey?.currentState != null) {
      navigateToIncidentDetails(
        context: navigatorKey!.currentState!.context,
        patientId: patientId,
        incidentType: alertType,
        incidentId: incidentId,
      );
    }
  }

  /// Show material dialog for foreground notification
  void _showNotificationDialog({
    required BuildContext context,
    required String title,
    required String body,
    required Map<String, dynamic> data,
  }) {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: Text(title),
          content: Text(body),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Dismiss'),
            ),
            TextButton(
              onPressed: () {
                Navigator.of(context).pop();
                _handleMessageTap(RemoteMessage(
                  data: data,
                  notification: RemoteNotification(
                    title: title,
                    body: body,
                  ),
                ));
              },
              child: const Text('View Details'),
            ),
          ],
        );
      },
    );
  }

  /// Send token to backend
  Future<void> _sendTokenToBackend(String token) async {
    try {
      print('📤 Sending token to backend: $token');
      // This should call your backend API to store the token
      // Example: await MonitoringApiService().registerDeviceToken(token);
    } catch (e) {
      print('❌ Failed to send token to backend: $e');
    }
  }

  static void navigateToIncidentDetails({
    required BuildContext context,
    required String patientId,
    required String incidentType,
    required String incidentId,
  }) {
    print('📍 Navigating to $incidentType incident details');
    print('   Patient: $patientId, Incident: $incidentId');
    
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => IncidentDetailsScreen(
          patientId: patientId,
          incidentType: incidentType,
          incidentId: incidentId,
        ),
      ),
    );
  }
}
