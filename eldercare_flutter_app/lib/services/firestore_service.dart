import 'package:cloud_firestore/cloud_firestore.dart';
import '../models/user.dart';
import '../models/elder.dart';
import '../models/alert.dart';

/// Service for Firestore database operations
class FirestoreService {
  static final FirebaseFirestore _db = FirebaseFirestore.instance;

  // ─────────────────────────────────────────────────────────
  // USER OPERATIONS
  // ─────────────────────────────────────────────────────────

  /// Create user document in Firestore
  Future<void> createUser({
    required String userId,
    required String email,
    required String name,
    required String role, // 'CAREGIVER' or 'ELDER'
    String? phone,
  }) async {
    try {
      final user = AppUser(
        userId: userId,
        email: email,
        name: name,
        role: role,
        phone: phone,
        createdAt: DateTime.now(),
        updatedAt: DateTime.now(),
      );

      await _db.collection('users').doc(userId).set(user.toJson());
    } catch (e) {
      throw 'Failed to create user: $e';
    }
  }

  /// Get current user document
  Future<AppUser?> getUser(String userId) async {
    try {
      final doc = await _db.collection('users').doc(userId).get();
      if (doc.exists) {
        return AppUser.fromJson(doc.data() as Map<String, dynamic>);
      }
      return null;
    } catch (e) {
      throw 'Failed to get user: $e';
    }
  }

  /// Update user email for alerts
  Future<void> updateUserEmail({
    required String userId,
    required String email,
  }) async {
    try {
      await _db.collection('users').doc(userId).update({
        'email': email,
        'updatedAt': DateTime.now().toIso8601String(),
      });
    } catch (e) {
      throw 'Failed to update email: $e';
    }
  }

  /// Update user phone
  Future<void> updateUserPhone({
    required String userId,
    required String phone,
  }) async {
    try {
      await _db.collection('users').doc(userId).update({
        'phone': phone,
        'updatedAt': DateTime.now().toIso8601String(),
      });
    } catch (e) {
      throw 'Failed to update phone: $e';
    }
  }

  // ─────────────────────────────────────────────────────────
  // ELDER OPERATIONS
  // ─────────────────────────────────────────────────────────

  /// Create elder document
  Future<String> createElder({
    required String caregiverId,
    required String name,
    required int age,
    required String gender,
    required List<String> medicalConditions,
    String? allergies,
    String? medications,
    required String emergencyContactName,
    required String emergencyContactPhone,
    String? healthcareProviderContact,
  }) async {
    try {
      final elder = Elder(
        elderId: '', // Will be set by Firestore
        name: name,
        age: age,
        gender: gender,
        medicalConditions: medicalConditions,
        allergies: allergies,
        medications: medications,
        emergencyContactName: emergencyContactName,
        emergencyContactPhone: emergencyContactPhone,
        healthcareProviderContact: healthcareProviderContact,
        assignedCaregiverIds: [caregiverId],
        deviceTokens: [],
        alertThresholds: {
          'fall_confidence': 0.75,
          'inactivity_minutes': 120,
          'sleep_hours': 15,
        },
        createdAt: DateTime.now(),
        updatedAt: DateTime.now(),
      );

      final docRef = await _db.collection('elders').add(elder.toJson());
      
      // Update the document with its ID
      await _db.collection('elders').doc(docRef.id).update({
        'elderId': docRef.id,
      });

      return docRef.id;
    } catch (e) {
      throw 'Failed to create elder: $e';
    }
  }

  /// Get elder by ID
  Future<Elder?> getElder(String elderId) async {
    try {
      final doc = await _db.collection('elders').doc(elderId).get();
      if (doc.exists) {
        return Elder.fromJson(doc.data() as Map<String, dynamic>, elderId);
      }
      return null;
    } catch (e) {
      throw 'Failed to get elder: $e';
    }
  }

  /// Get all elders assigned to a caregiver
  Future<List<Elder>> getEldersForCaregiver(String caregiverId) async {
    try {
      final query = await _db
          .collection('elders')
          .where('assignedCaregiverIds', arrayContains: caregiverId)
          .get();

      return query.docs
          .map((doc) => Elder.fromJson(doc.data(), doc.id))
          .toList();
    } catch (e) {
      throw 'Failed to get elders: $e';
    }
  }

  /// Update elder information
  Future<void> updateElder({
    required String elderId,
    required Map<String, dynamic> updates,
  }) async {
    try {
      updates['updatedAt'] = DateTime.now().toIso8601String();
      await _db.collection('elders').doc(elderId).update(updates);
    } catch (e) {
      throw 'Failed to update elder: $e';
    }
  }

  /// Add device token to elder
  Future<void> addDeviceToken({
    required String elderId,
    required String deviceToken,
  }) async {
    try {
      await _db.collection('elders').doc(elderId).update({
        'deviceTokens': FieldValue.arrayUnion([deviceToken]),
        'updatedAt': DateTime.now().toIso8601String(),
      });
    } catch (e) {
      throw 'Failed to add device token: $e';
    }
  }

  /// Add caregiver to elder
  Future<void> addCaregiverToElder({
    required String elderId,
    required String caregiverId,
  }) async {
    try {
      await _db.collection('elders').doc(elderId).update({
        'assignedCaregiverIds': FieldValue.arrayUnion([caregiverId]),
        'updatedAt': DateTime.now().toIso8601String(),
      });
    } catch (e) {
      throw 'Failed to add caregiver: $e';
    }
  }

  // ─────────────────────────────────────────────────────────
  // ALERT OPERATIONS
  // ─────────────────────────────────────────────────────────

  /// Create alert document
  Future<String> createAlert({
    required String elderId,
    required String alertType,
    required String activityLabel,
    required double confidence,
    required String message,
  }) async {
    try {
      final alert = AppAlert(
        alertId: '', // Will be set by Firestore
        elderId: elderId,
        alertType: alertType,
        activityLabel: activityLabel,
        confidence: confidence,
        message: message,
        timestamp: DateTime.now(),
      );

      final docRef = await _db
          .collection('alerts')
          .doc(elderId)
          .collection('events')
          .add(alert.toJson());

      return docRef.id;
    } catch (e) {
      throw 'Failed to create alert: $e';
    }
  }

  /// Get alerts for elder
  Future<List<AppAlert>> getAlertsForElder(
    String elderId, {
    int limit = 50,
  }) async {
    try {
      final query = await _db
          .collection('alerts')
          .doc(elderId)
          .collection('events')
          .orderBy('timestamp', descending: true)
          .limit(limit)
          .get();

      return query.docs
          .map((doc) => AppAlert.fromJson(doc.data(), doc.id))
          .toList();
    } catch (e) {
      throw 'Failed to get alerts: $e';
    }
  }

  /// Acknowledge alert
  Future<void> acknowledgeAlert({
    required String elderId,
    required String alertId,
    required String userId,
  }) async {
    try {
      await _db
          .collection('alerts')
          .doc(elderId)
          .collection('events')
          .doc(alertId)
          .update({
            'acknowledged': true,
            'acknowledgedBy': userId,
            'acknowledgedAt': DateTime.now().toIso8601String(),
          });
    } catch (e) {
      throw 'Failed to acknowledge alert: $e';
    }
  }

  // ─────────────────────────────────────────────────────────
  // ACTIVITY LOG OPERATIONS
  // ─────────────────────────────────────────────────────────

  /// Log activity
  Future<String> logActivity({
    required String elderId,
    required String activityLabel,
    required int durationSeconds,
    required double confidence,
  }) async {
    try {
      final docRef = await _db
          .collection('activity_log')
          .doc(elderId)
          .collection('activities')
          .add({
            'activity_label': activityLabel,
            'duration_seconds': durationSeconds,
            'confidence': confidence,
            'timestamp': DateTime.now().toIso8601String(),
          });

      return docRef.id;
    } catch (e) {
      throw 'Failed to log activity: $e';
    }
  }

  /// Get activity logs for elder
  Future<List<Map<String, dynamic>>> getActivityLogs(
    String elderId, {
    int limit = 100,
  }) async {
    try {
      final query = await _db
          .collection('activity_log')
          .doc(elderId)
          .collection('activities')
          .orderBy('timestamp', descending: true)
          .limit(limit)
          .get();

      return query.docs.map((doc) => doc.data()).toList();
    } catch (e) {
      throw 'Failed to get activity logs: $e';
    }
  }

  // ─────────────────────────────────────────────────────────
  // STREAMING
  // ─────────────────────────────────────────────────────────

  /// Stream of alerts for elder (real-time)
  Stream<List<AppAlert>> streamAlertsForElder(String elderId) {
    return _db
        .collection('alerts')
        .doc(elderId)
        .collection('events')
        .orderBy('timestamp', descending: true)
        .limit(50)
        .snapshots()
        .map((snapshot) => snapshot.docs
            .map((doc) => AppAlert.fromJson(doc.data(), doc.id))
            .toList());
  }

  /// Stream of elder data (real-time)
  Stream<Elder?> streamElder(String elderId) {
    return _db
        .collection('elders')
        .doc(elderId)
        .snapshots()
        .map((doc) => doc.exists
            ? Elder.fromJson(doc.data() as Map<String, dynamic>, elderId)
            : null);
  }
}
