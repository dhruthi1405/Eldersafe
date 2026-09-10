/// User model representing a caregiver or elder
class AppUser {
  final String userId;
  final String email;
  final String name;
  final String role; // 'CAREGIVER' or 'ELDER'
  final String? phone;
  final DateTime createdAt;
  final DateTime? updatedAt;

  AppUser({
    required this.userId,
    required this.email,
    required this.name,
    required this.role,
    this.phone,
    required this.createdAt,
    this.updatedAt,
  });

  /// Convert to JSON for Firestore
  Map<String, dynamic> toJson() {
    return {
      'userId': userId,
      'email': email,
      'name': name,
      'role': role,
      'phone': phone,
      'createdAt': createdAt.toIso8601String(),
      'updatedAt': updatedAt?.toIso8601String(),
    };
  }

  /// Create from Firestore document
  factory AppUser.fromJson(Map<String, dynamic> json) {
    return AppUser(
      userId: json['userId'] ?? '',
      email: json['email'] ?? '',
      name: json['name'] ?? '',
      role: json['role'] ?? 'CAREGIVER',
      phone: json['phone'],
      createdAt: DateTime.parse(json['createdAt'] ?? DateTime.now().toIso8601String()),
      updatedAt: json['updatedAt'] != null ? DateTime.parse(json['updatedAt']) : null,
    );
  }

  /// Create a copy with modified fields
  AppUser copyWith({
    String? userId,
    String? email,
    String? name,
    String? role,
    String? phone,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return AppUser(
      userId: userId ?? this.userId,
      email: email ?? this.email,
      name: name ?? this.name,
      role: role ?? this.role,
      phone: phone ?? this.phone,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  @override
  String toString() => 'AppUser(id: $userId, email: $email, role: $role)';
}
