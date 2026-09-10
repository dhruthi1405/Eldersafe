import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/activity.dart';

/// Service to manage activity tracking and persistence
class ActivityService {
  static const String _activitiesKey = 'activities_timeline';
  static const int _maxActivities = 200;

  /// Get all activities from storage
  static Future<List<Activity>> getActivities() async {
    final prefs = await SharedPreferences.getInstance();
    final activitiesJson = prefs.getString(_activitiesKey);

    if (activitiesJson == null) {
      return [];
    }

    try {
      final List<dynamic> decoded = jsonDecode(activitiesJson);
      return decoded
          .map((item) => Activity.fromJson(item as Map<String, dynamic>))
          .toList();
    } catch (e) {
      print('Error decoding activities: $e');
      return [];
    }
  }

  /// Add new activity to timeline
  static Future<void> addActivity(Activity activity) async {
    final prefs = await SharedPreferences.getInstance();
    final activities = await getActivities();

    // Insert at beginning (most recent first)
    activities.insert(0, activity);

    // Keep only last N activities
    if (activities.length > _maxActivities) {
      activities.removeRange(_maxActivities, activities.length);
    }

    final activitiesJson = jsonEncode(
      activities.map((a) => a.toJson()).toList(),
    );
    await prefs.setString(_activitiesKey, activitiesJson);
  }

  /// Get activities grouped by type
  static Future<Map<String, List<Activity>>> getActivitiesByType() async {
    final activities = await getActivities();
    final grouped = <String, List<Activity>>{};

    for (var activity in activities) {
      if (!grouped.containsKey(activity.label)) {
        grouped[activity.label] = [];
      }
      grouped[activity.label]!.add(activity);
    }

    return grouped;
  }

  /// Get activity statistics
  static Future<ActivityStats> getActivityStats() async {
    final activities = await getActivities();
    final stats = ActivityStats();

    for (var activity in activities) {
      stats.addActivity(activity);
    }

    return stats;
  }

  /// Get activities from last N hours
  static Future<List<Activity>> getRecentActivities(int hours) async {
    final activities = await getActivities();
    final cutoff = DateTime.now().subtract(Duration(hours: hours));

    return activities.where((a) => a.timestamp.isAfter(cutoff)).toList();
  }

  /// Clear all activities
  static Future<void> clearActivities() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_activitiesKey);
  }

  /// Get current activity (most recent)
  static Future<Activity?> getCurrentActivity() async {
    final activities = await getActivities();
    return activities.isNotEmpty ? activities.first : null;
  }

  /// Get total time spent in each activity today
  static Future<Map<String, int>> getTodayActivityDuration() async {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);

    final activities = await getActivities();
    final todayActivities =
        activities.where((a) => a.timestamp.isAfter(today)).toList();

    final durations = <String, int>{};
    for (var activity in todayActivities) {
      durations[activity.label] =
          (durations[activity.label] ?? 0) + activity.durationSeconds;
    }

    return durations;
  }
}

/// Statistics about activities
class ActivityStats {
  final Map<String, int> totalDurationByType = {};
  final Map<String, int> countByType = {};
  final Map<String, double> avgConfidenceByType = {};
  final Map<String, int> confidenceCountByType = {};

  void addActivity(Activity activity) {
    final label = activity.label;

    // Duration
    totalDurationByType[label] =
        (totalDurationByType[label] ?? 0) + activity.durationSeconds;

    // Count
    countByType[label] = (countByType[label] ?? 0) + 1;

    // Average confidence
    confidenceCountByType[label] =
        (confidenceCountByType[label] ?? 0) + 1;
    final avgConf = avgConfidenceByType[label] ?? 0.0;
    final newAvg =
        (avgConf * (confidenceCountByType[label]! - 1) + activity.confidence) /
            confidenceCountByType[label]!;
    avgConfidenceByType[label] = newAvg;
  }

  /// Get total time spent in activity (formatted)
  String getDurationFormatted(String activityLabel) {
    final seconds = totalDurationByType[activityLabel] ?? 0;
    final hours = seconds ~/ 3600;
    final minutes = (seconds % 3600) ~/ 60;
    final secs = seconds % 60;

    if (hours > 0) {
      return '${hours}h ${minutes}m';
    } else if (minutes > 0) {
      return '${minutes}m';
    } else {
      return '${secs}s';
    }
  }

  /// Sort activities by total duration
  List<String> get sortedActivitiesByDuration {
    final sorted = totalDurationByType.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    return sorted.map((e) => e.key).toList();
  }
}
