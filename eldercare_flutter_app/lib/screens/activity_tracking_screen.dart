import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../models/activity.dart';
import '../services/activity_service.dart';

class ActivityTrackingScreen extends StatefulWidget {
  const ActivityTrackingScreen({Key? key}) : super(key: key);

  @override
  State<ActivityTrackingScreen> createState() => _ActivityTrackingScreenState();
}

class _ActivityTrackingScreenState extends State<ActivityTrackingScreen> {
  List<Activity> _activities = [];
  ActivityStats? _stats;
  bool _isLoading = true;
  int _selectedHours = 24; // Show last 24 hours by default

  @override
  void initState() {
    super.initState();
    _loadActivities();
  }

  Future<void> _loadActivities() async {
    setState(() => _isLoading = true);

    final activities =
        await ActivityService.getRecentActivities(_selectedHours);
    final stats = await ActivityService.getActivityStats();

    setState(() {
      _activities = activities;
      _stats = stats;
      _isLoading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Activity Timeline'),
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadActivities,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Time Range Selector
                  Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Row(
                      children: [
                        const Text(
                          'Show last:',
                          style: TextStyle(fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(width: 12),
                        _buildTimeRangeButton(6, '6h'),
                        _buildTimeRangeButton(12, '12h'),
                        _buildTimeRangeButton(24, '24h'),
                        _buildTimeRangeButton(168, '7d'),
                      ],
                    ),
                  ),
                  // Statistics Summary
                  if (_stats != null) _buildStatisticsCard(),
                  // Activity Timeline
                  Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: const Text(
                      'Recent Activities',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                  if (_activities.isEmpty)
                    Center(
                      child: Padding(
                        padding: const EdgeInsets.all(32.0),
                        child: Text(
                          'No activities in the last $_selectedHours hours',
                          style: const TextStyle(color: Colors.grey),
                        ),
                      ),
                    )
                  else
                    ListView.builder(
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      itemCount: _activities.length,
                      itemBuilder: (context, index) {
                        final activity = _activities[index];
                        final isAlert = ['fall', 'wave'].contains(activity.label);

                        return Padding(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 16.0,
                            vertical: 8.0,
                          ),
                          child: GestureDetector(
                            onTap: () => _showActivityDetails(activity),
                            child: Card(
                              elevation: isAlert ? 4 : 1,
                              color: isAlert
                                  ? Color(
                                      int.parse(activity.colorHex(), radix: 16),
                                    )
                                  : Colors.white,
                              child: Padding(
                                padding: const EdgeInsets.all(12.0),
                                child: Row(
                                  children: [
                                    // Activity Icon
                                    Container(
                                      width: 48,
                                      height: 48,
                                      decoration: BoxDecoration(
                                        color: isAlert
                                            ? Colors.white.withOpacity(0.3)
                                            : Color(
                                                int.parse(
                                                  activity.colorHex(),
                                                  radix: 16,
                                                ),
                                              ).withOpacity(0.2),
                                        borderRadius:
                                            BorderRadius.circular(10),
                                      ),
                                      child: Center(
                                        child: Text(
                                          activity.icon,
                                          style: const TextStyle(
                                            fontSize: 24,
                                          ),
                                        ),
                                      ),
                                    ),
                                    const SizedBox(width: 12),
                                    // Activity Info
                                    Expanded(
                                      child: Column(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                            activity.displayLabel,
                                            style: TextStyle(
                                              fontSize: 16,
                                              fontWeight: FontWeight.bold,
                                              color: isAlert
                                                  ? Colors.white
                                                  : Colors.black,
                                            ),
                                          ),
                                          const SizedBox(height: 4),
                                          Text(
                                            DateFormat('MMM d, yyyy HH:mm:ss')
                                                .format(activity.timestamp),
                                            style: TextStyle(
                                              fontSize: 12,
                                              color: isAlert
                                                  ? Colors.white70
                                                  : Colors.grey[600],
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                    // Duration & Confidence
                                    Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.end,
                                      children: [
                                        Text(
                                          activity.durationFormatted,
                                          style: TextStyle(
                                            fontSize: 13,
                                            fontWeight: FontWeight.bold,
                                            color: isAlert
                                                ? Colors.white
                                                : Colors.black,
                                          ),
                                        ),
                                        const SizedBox(height: 4),
                                        Text(
                                          activity.confidenceFormatted,
                                          style: TextStyle(
                                            fontSize: 11,
                                            color: isAlert
                                                ? Colors.white70
                                                : Colors.grey[600],
                                          ),
                                        ),
                                      ],
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ),
                        );
                      },
                    ),
                  const SizedBox(height: 24),
                ],
              ),
            ),
    );
  }

  Widget _buildTimeRangeButton(int hours, String label) {
    final isSelected = _selectedHours == hours;

    return Padding(
      padding: const EdgeInsets.only(right: 8.0),
      child: MaterialButton(
        onPressed: () {
          setState(() => _selectedHours = hours);
          _loadActivities();
        },
        color: isSelected ? Colors.blue : Colors.grey[200],
        textColor: isSelected ? Colors.white : Colors.black,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(6),
        ),
        height: 32,
        minWidth: 40,
        child: Text(
          label,
          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold),
        ),
      ),
    );
  }

  Widget _buildStatisticsCard() {
    final sortedActivities = _stats!.sortedActivitiesByDuration;

    return Padding(
      padding: const EdgeInsets.all(16.0),
      child: Card(
        elevation: 2,
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                '📊 Activity Summary',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 12),
              ...sortedActivities.take(5).map((label) {
                final activity = Activity(
                  id: label,
                  label: label,
                  timestamp: DateTime.now(),
                  confidence: _stats!.avgConfidenceByType[label] ?? 0,
                  durationSeconds: _stats!.totalDurationByType[label] ?? 0,
                );

                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6.0),
                  child: Row(
                    children: [
                      Text(
                        activity.icon,
                        style: const TextStyle(fontSize: 18),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          activity.displayLabel,
                          style: const TextStyle(
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                      Text(
                        _stats!.getDurationFormatted(label),
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          color: Color(
                            int.parse(activity.colorHex(), radix: 16),
                          ),
                        ),
                      ),
                    ],
                  ),
                );
              }).toList(),
            ],
          ),
        ),
      ),
    );
  }

  void _showActivityDetails(Activity activity) {
    showModalBottomSheet(
      context: context,
      builder: (context) => Container(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Text(
                activity.icon,
                style: const TextStyle(fontSize: 48),
              ),
            ),
            const SizedBox(height: 16),
            Text(
              activity.displayLabel,
              style: const TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 12),
            _buildDetailRow('Timestamp',
                DateFormat('yyyy-MM-dd HH:mm:ss').format(activity.timestamp)),
            _buildDetailRow('Duration', activity.durationFormatted),
            _buildDetailRow('Confidence', activity.confidenceFormatted),
            if (activity.notes != null)
              _buildDetailRow('Notes', activity.notes!),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Close'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDetailRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: const TextStyle(
              color: Colors.grey,
              fontWeight: FontWeight.w500,
            ),
          ),
          Text(
            value,
            style: const TextStyle(
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }
}
