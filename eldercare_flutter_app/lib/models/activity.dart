/// Activity data model for tracking elder's activities
class Activity {
  final String id;
  final String label; // walk, sit, stand, eat, sleep, fall, wave
  final DateTime timestamp;
  final double confidence; // 0.0 - 1.0
  final int durationSeconds; // How long activity lasted
  final String? notes;

  Activity({
    required this.id,
    required this.label,
    required this.timestamp,
    required this.confidence,
    required this.durationSeconds,
    this.notes,
  });

  /// Convert from Firebase/backend JSON
  factory Activity.fromJson(Map<String, dynamic> json) {
    return Activity(
      id: json['id'] ?? '',
      label: json['label'] ?? 'unknown',
      timestamp: DateTime.parse(json['timestamp'] ?? DateTime.now().toIso8601String()),
      confidence: (json['confidence'] ?? 0.0).toDouble(),
      durationSeconds: json['duration_seconds'] ?? 0,
      notes: json['notes'],
    );
  }

  /// Convert to JSON for storage
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'label': label,
      'timestamp': timestamp.toIso8601String(),
      'confidence': confidence,
      'duration_seconds': durationSeconds,
      'notes': notes,
    };
  }

  /// Get human-readable label
  String get displayLabel {
    switch (label.toLowerCase()) {
      case 'walk':
        return 'Walking';
      case 'sit':
        return 'Sitting';
      case 'stand':
        return 'Standing';
      case 'eat':
        return 'Eating';
      case 'sleep':
        return 'Sleeping';
      case 'fall':
        return '⚠️ FALL';
      case 'wave':
        return '🆘 SOS Wave';
      default:
        return label[0].toUpperCase() + label.substring(1);
    }
  }

  /// Get emoji icon for activity
  String get icon {
    switch (label.toLowerCase()) {
      case 'walk':
        return '🚶';
      case 'sit':
        return '🪑';
      case 'stand':
        return '🧍';
      case 'eat':
        return '🍽️';
      case 'sleep':
        return '😴';
      case 'fall':
        return '⚠️';
      case 'wave':
        return '🆘';
      default:
        return '📊';
    }
  }

  /// Get color for activity
  String get color {
    switch (label.toLowerCase()) {
      case 'walk':
        return '#4CAF50'; // Green
      case 'sit':
        return '#2196F3'; // Blue
      case 'stand':
        return '#FF9800'; // Orange
      case 'eat':
        return '#F44336'; // Red
      case 'sleep':
        return '#9C27B0'; // Purple
      case 'fall':
        return '#FF3B3B'; // Dark Red
      case 'wave':
        return '#FF8C00'; // Dark Orange
      default:
        return '#9E9E9E'; // Gray
    }
  }

  /// Get material color
  String colorHex() => color.replaceFirst('#', '0xFF');

  /// Duration as HH:MM:SS format
  String get durationFormatted {
    final hours = durationSeconds ~/ 3600;
    final minutes = (durationSeconds % 3600) ~/ 60;
    final seconds = durationSeconds % 60;

    if (hours > 0) {
      return '$hours:${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}';
    } else if (minutes > 0) {
      return '${minutes}m ${seconds}s';
    } else {
      return '${seconds}s';
    }
  }

  /// Confidence as percentage
  String get confidenceFormatted => '${(confidence * 100).toStringAsFixed(1)}%';
}
