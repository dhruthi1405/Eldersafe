/// Elder person model for monitoring
class Elder {
  final String elderId;
  final String name;
  final int age;
  final String gender; // 'MALE', 'FEMALE', 'OTHER'
  final List<String> medicalConditions;
  final String? allergies;
  final String? medications;
  final String emergencyContactName;
  final String emergencyContactPhone;
  final String? healthcareProviderContact;
  final List<String> assignedCaregiverIds; // Caregiver user IDs
  final List<String> deviceTokens; // Firebase device tokens for push notifications
  final Map<String, dynamic> alertThresholds;
  final DateTime createdAt;
  final DateTime? updatedAt;

  Elder({
    required this.elderId,
    required this.name,
    required this.age,
    required this.gender,
    required this.medicalConditions,
    this.allergies,
    this.medications,
    required this.emergencyContactName,
    required this.emergencyContactPhone,
    this.healthcareProviderContact,
    required this.assignedCaregiverIds,
    required this.deviceTokens,
    required this.alertThresholds,
    required this.createdAt,
    this.updatedAt,
  });

  /// Convert to JSON for Firestore
  Map<String, dynamic> toJson() {
    return {
      'elderId': elderId,
      'name': name,
      'age': age,
      'gender': gender,
      'medicalConditions': medicalConditions,
      'allergies': allergies,
      'medications': medications,
      'emergencyContactName': emergencyContactName,
      'emergencyContactPhone': emergencyContactPhone,
      'healthcareProviderContact': healthcareProviderContact,
      'assignedCaregiverIds': assignedCaregiverIds,
      'deviceTokens': deviceTokens,
      'alertThresholds': alertThresholds,
      'createdAt': createdAt.toIso8601String(),
      'updatedAt': updatedAt?.toIso8601String(),
    };
  }

  /// Create from Firestore document
  factory Elder.fromJson(Map<String, dynamic> json, String docId) {
    return Elder(
      elderId: json['elderId'] ?? docId,
      name: json['name'] ?? '',
      age: json['age'] ?? 0,
      gender: json['gender'] ?? 'OTHER',
      medicalConditions: List<String>.from(json['medicalConditions'] ?? []),
      allergies: json['allergies'],
      medications: json['medications'],
      emergencyContactName: json['emergencyContactName'] ?? '',
      emergencyContactPhone: json['emergencyContactPhone'] ?? '',
      healthcareProviderContact: json['healthcareProviderContact'],
      assignedCaregiverIds: List<String>.from(json['assignedCaregiverIds'] ?? []),
      deviceTokens: List<String>.from(json['deviceTokens'] ?? []),
      alertThresholds: Map<String, dynamic>.from(json['alertThresholds'] ?? {}),
      createdAt: DateTime.parse(json['createdAt'] ?? DateTime.now().toIso8601String()),
      updatedAt: json['updatedAt'] != null ? DateTime.parse(json['updatedAt']) : null,
    );
  }

  /// Create a copy with modified fields
  Elder copyWith({
    String? elderId,
    String? name,
    int? age,
    String? gender,
    List<String>? medicalConditions,
    String? allergies,
    String? medications,
    String? emergencyContactName,
    String? emergencyContactPhone,
    String? healthcareProviderContact,
    List<String>? assignedCaregiverIds,
    List<String>? deviceTokens,
    Map<String, dynamic>? alertThresholds,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return Elder(
      elderId: elderId ?? this.elderId,
      name: name ?? this.name,
      age: age ?? this.age,
      gender: gender ?? this.gender,
      medicalConditions: medicalConditions ?? this.medicalConditions,
      allergies: allergies ?? this.allergies,
      medications: medications ?? this.medications,
      emergencyContactName: emergencyContactName ?? this.emergencyContactName,
      emergencyContactPhone: emergencyContactPhone ?? this.emergencyContactPhone,
      healthcareProviderContact: healthcareProviderContact ?? this.healthcareProviderContact,
      assignedCaregiverIds: assignedCaregiverIds ?? this.assignedCaregiverIds,
      deviceTokens: deviceTokens ?? this.deviceTokens,
      alertThresholds: alertThresholds ?? this.alertThresholds,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  @override
  String toString() => 'Elder(id: $elderId, name: $name, age: $age)';
}
