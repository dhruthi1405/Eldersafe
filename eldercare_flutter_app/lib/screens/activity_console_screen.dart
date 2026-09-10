import 'package:flutter/material.dart';
import '../utils/activity_sample_generator.dart';
import '../services/activity_service.dart';
import '../models/activity.dart';

class ActivityConsoleScreen extends StatefulWidget {
  const ActivityConsoleScreen({Key? key}) : super(key: key);

  @override
  State<ActivityConsoleScreen> createState() => _ActivityConsoleScreenState();
}

class _ActivityConsoleScreenState extends State<ActivityConsoleScreen> {
  String _output = 'Activity Console\n\n';
  int _totalActivities = 0;

  @override
  void initState() {
    super.initState();
    _loadStats();
  }

  Future<void> _loadStats() async {
    final activities = await ActivityService.getActivities();
    setState(() {
      _totalActivities = activities.length;
      _output += '📊 Loaded $_totalActivities activities from storage\n';
    });
  }

  Future<void> _generateSampleData() async {
    _log('🔄 Generating sample activities...');
    await ActivitySampleGenerator.generateSampleActivities();
    await _loadStats();
    _log('✓ Sample data generated');
  }

  Future<void> _addRandomActivity() async {
    _log('➕ Adding random activity...');
    await ActivitySampleGenerator.addRandomActivity();
    await _loadStats();
    _log('✓ Random activity added');
  }

  Future<void> _clearAllActivities() async {
    _log('🗑️  Clearing all activities...');
    await ActivitySampleGenerator.clearAllActivities();
    setState(() {
      _totalActivities = 0;
    });
    _log('✓ All activities cleared');
  }

  Future<void> _showStats() async {
    _log('📈 Activity Statistics:');
    final stats = await ActivityService.getActivityStats();

    for (final label in stats.sortedActivitiesByDuration) {
      final count = stats.countByType[label] ?? 0;
      final duration = stats.getDurationFormatted(label);
      final avgConf =
          (stats.avgConfidenceByType[label] ?? 0.0) * 100;

      _log('  $label: $count times, $duration, ${avgConf.toStringAsFixed(1)}% confidence');
    }
  }

  void _log(String message) {
    setState(() {
      _output += '$message\n';
    });
  }

  void _clearLog() {
    setState(() {
      _output = 'Activity Console\n\n';
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Activity Console (Dev)'),
        actions: [
          IconButton(
            icon: const Icon(Icons.delete),
            onPressed: _clearLog,
            tooltip: 'Clear log',
          ),
        ],
      ),
      body: Column(
        children: [
          // Output Log
          Expanded(
            child: Container(
              margin: const EdgeInsets.all(16),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.black87,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.green),
              ),
              child: SingleChildScrollView(
                child: SelectableText(
                  _output,
                  style: const TextStyle(
                    color: Colors.green,
                    fontFamily: 'Courier New',
                    fontSize: 12,
                  ),
                ),
              ),
            ),
          ),
          // Buttons
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                ElevatedButton.icon(
                  onPressed: _generateSampleData,
                  icon: const Icon(Icons.data_array),
                  label: const Text('Generate\nSample Data'),
                ),
                ElevatedButton.icon(
                  onPressed: _addRandomActivity,
                  icon: const Icon(Icons.add),
                  label: const Text('Add Random\nActivity'),
                ),
                ElevatedButton.icon(
                  onPressed: _showStats,
                  icon: const Icon(Icons.analytics),
                  label: const Text('Show\nStats'),
                ),
                ElevatedButton.icon(
                  onPressed: _clearAllActivities,
                  icon: const Icon(Icons.delete_forever),
                  label: const Text('Clear\nAll'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.red,
                  ),
                ),
                ElevatedButton.icon(
                  onPressed: _loadStats,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Refresh\nStats'),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
