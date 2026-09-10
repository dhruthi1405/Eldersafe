import 'package:flutter/material.dart';

/// Alert event model
class AppAlert {
  final String alertId;
  final String elderId;
  final String alertType; // 'FALL', 'SOS', 'INACTIVITY', 'ACTIVITY', 'SLEEP'
  final String activityLabel;
  final double confidence;
  final String message;
  final DateTime timestamp;
  final bool acknowledged;
  final String? acknowledgedBy;
  final DateTime? acknowledgedAt;

  AppAlert({
    required this.alertId,
    required this.elderId,
    required this.alertType,
    required this.activityLabel,
    required this.confidence,
    required this.message,
    required this.timestamp,
    this.acknowledged = false,
    this.acknowledgedBy,
    this.acknowledgedAt,
  });

  /// Convert to JSON for Firestore
  Map<String, dynamic> toJson() {
    return {
      'alertId': alertId,
      'elderId': elderId,
      'alertType': alertType,
      'activityLabel': activityLabel,
      'confidence': confidence,
      'message': message,
      'timestamp': timestamp.toIso8601String(),
      'acknowledged': acknowledged,
      'acknowledgedBy': acknowledgedBy,
      'acknowledgedAt': acknowledgedAt?.toIso8601String(),
    };
  }

  /// Create from Firestore document
  factory AppAlert.fromJson(Map<String, dynamic> json, String docId) {
    return AppAlert(
      alertId: json['alertId'] ?? docId,
      elderId: json['elderId'] ?? '',
      alertType: json['alertType'] ?? 'ACTIVITY',
      activityLabel: json['activityLabel'] ?? '',
      confidence: (json['confidence'] ?? 0.0).toDouble(),
      message: json['message'] ?? '',
      timestamp: DateTime.parse(json['timestamp'] ?? DateTime.now().toIso8601String()),
      acknowledged: json['acknowledged'] ?? false,
      acknowledgedBy: json['acknowledgedBy'],
      acknowledgedAt: json['acknowledgedAt'] != null 
        ? DateTime.parse(json['acknowledgedAt']) 
        : null,
    );
  }

  /// Get alert icon
  IconData get icon {
    switch (alertType) {
      case 'FALL':
        return Icons.warning_amber;
      case 'SOS':
        return Icons.emergency;
      case 'INACTIVITY':
        return Icons.pause_circle;
      case 'SLEEP':
        return Icons.hotel;
      default:
        return Icons.notifications;
    }
  }

  /// Get alert color
  Color get color {
    switch (alertType) {
      case 'FALL':
        return Colors.red;
      case 'SOS':
        return Colors.redAccent;
      case 'INACTIVITY':
        return Colors.grey;
      case 'SLEEP':
        return Colors.purple;
      default:
        return Colors.blue;
    }
  }

  /// Mark alert as acknowledged
  AppAlert acknowledge(String userId) {
    return AppAlert(
      alertId: alertId,
      elderId: elderId,
      alertType: alertType,
      activityLabel: activityLabel,
      confidence: confidence,
      message: message,
      timestamp: timestamp,
      acknowledged: true,
      acknowledgedBy: userId,
      acknowledgedAt: DateTime.now(),
    );
  }

  @override
  String toString() => 'AppAlert(id: $alertId, type: $alertType, elder: $elderId)';
}
