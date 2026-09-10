import 'package:uuid/uuid.dart';
import '../models/activity.dart';
import '../services/activity_service.dart';

/// Helper class to generate sample activities for testing/demo
class ActivitySampleGenerator {
  static const uuid = Uuid();

  /// Generate realistic sample activities for testing
  /// This creates activities across the last 24 hours
  static Future<void> generateSampleActivities() async {
    final now = DateTime.now();

    // Sample activity data structure: [activity, duration in minutes, confidence]
    final activities = [
      // Last 24 hours timeline
      ['sleep', 480, 0.95], // 8 hours sleep at night
      ['walk', 15, 0.89],
      ['eat', 25, 0.92],
      ['sit', 120, 0.88],
      ['stand', 45, 0.90],
      ['walk', 20, 0.87],
      ['sit', 60, 0.91],
      ['eat', 20, 0.93],
      ['stand', 30, 0.89],
      ['walk', 25, 0.88],
      ['sit', 90, 0.85],
      ['stand', 20, 0.90],
      ['walk', 15, 0.92],
      ['sit', 120, 0.87],
      ['stand', 25, 0.91],
      ['eat', 30, 0.89],
      ['walk', 20, 0.88],
      ['sit', 60, 0.90],
    ];

    // Add activities starting from 24 hours ago
    var currentTime = now.subtract(const Duration(hours: 24));

    for (final activityData in activities) {
      final activity = Activity(
        id: uuid.v4(),
        label: activityData[0] as String,
        timestamp: currentTime,
        confidence: (activityData[2] as num).toDouble(),
        durationSeconds: (activityData[1] as int) * 60,
      );

      await ActivityService.addActivity(activity);

      // Move time forward
      currentTime =
          currentTime.add(Duration(minutes: activityData[1] as int));
    }

    print('✓ Generated ${activities.length} sample activities');
  }

  /// Add a single test activity
  static Future<void> addTestActivity(String label, int durationSeconds) async {
    final activity = Activity(
      id: uuid.v4(),
      label: label,
      timestamp: DateTime.now(),
      confidence: 0.85 + (DateTime.now().millisecond / 1000) * 0.15,
      durationSeconds: durationSeconds,
    );

    await ActivityService.addActivity(activity);
    print('✓ Added test activity: $label (${activity.durationFormatted})');
  }

  /// Simulate continuous activity for testing
  /// Call this periodically to add activities
  static Future<void> addRandomActivity() async {
    final activities = ['walk', 'sit', 'stand', 'eat'];
    final random = (DateTime.now().millisecond % activities.length);
    final activity = activities[random];

    final duration = 300 + (DateTime.now().millisecond % 300); // 5-10 minutes

    await addTestActivity(activity, duration);
  }

  /// Clear all sample data
  static Future<void> clearAllActivities() async {
    await ActivityService.clearActivities();
    print('✓ Cleared all activities');
  }
}
