import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../services/monitoring_api_service.dart';
import 'incident_details_screen.dart';

class AlertsScreen extends StatefulWidget {
  const AlertsScreen({Key? key}) : super(key: key);

  @override
  State<AlertsScreen> createState() => _AlertsScreenState();
}

class _AlertsScreenState extends State<AlertsScreen> {
  late MonitoringApiService _apiService;
  List<Map<String, dynamic>> _alerts = [];
  bool _isLoading = true;
  bool _autoRefresh = true;

  @override
  void initState() {
    super.initState();
    _apiService = MonitoringApiService();
    _loadAlerts();
    _startAutoRefresh();
  }

  void _startAutoRefresh() {
    Future.delayed(const Duration(seconds: 5), () {
      if (mounted && _autoRefresh) {
        _loadAlerts();
        _startAutoRefresh();
      }
    });
  }

  Future<void> _loadAlerts() async {
    try {
      final alerts = await _apiService.getRecentAlerts(limit: 50);
      if (mounted) {
        setState(() {
          _alerts = alerts;
          _isLoading = false;
        });
      }
    } catch (e) {
      print('Error loading alerts: $e');
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  @override
  void dispose() {
    _autoRefresh = false;
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Recent Alerts'),
        centerTitle: true,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadAlerts,
            tooltip: 'Refresh',
          ),
          IconButton(
            icon: const Icon(Icons.more_vert),
            onPressed: () => _showFilterMenu(),
            tooltip: 'Filter',
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _alerts.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        Icons.notifications_off,
                        size: 64,
                        color: Colors.grey[400],
                      ),
                      const SizedBox(height: 16),
                      Text(
                        'No alerts',
                        style: TextStyle(
                          fontSize: 18,
                          color: Colors.grey[600],
                        ),
                      ),
                    ],
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _loadAlerts,
                  child: ListView.builder(
                    itemCount: _alerts.length,
                    itemBuilder: (context, index) {
                      return _buildAlertTile(_alerts[index]);
                    },
                  ),
                ),
    );
  }

  Widget _buildAlertTile(Map<String, dynamic> alert) {
    final timestamp = DateTime.parse(alert['timestamp']);
    final timeAgo = _getTimeAgo(timestamp);
    final alertType = alert['alert_type'] ?? 'Unknown';
    final patientName = alert['patient_name'] ?? 'Unknown Patient';
    final severity = alert['severity'] ?? 'INFO';

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: ListTile(
        leading: _getAlertIcon(alertType),
        title: Text(
          alertType,
          style: const TextStyle(fontWeight: FontWeight.bold),
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 4),
            Text(
              patientName,
              style: const TextStyle(fontSize: 12, color: Colors.grey),
            ),
            Text(
              timeAgo,
              style: const TextStyle(fontSize: 11, color: Colors.grey),
            ),
          ],
        ),
        trailing: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: _getSeverityColor(severity),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                severity,
                style: const TextStyle(
                  fontSize: 10,
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            const SizedBox(height: 4),
            const Icon(Icons.chevron_right, size: 16),
          ],
        ),
        onTap: () => _navigateToDetails(alert),
      ),
    );
  }

  void _navigateToDetails(Map<String, dynamic> alert) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => IncidentDetailsScreen(
          patientId: alert['patient_id'] ?? '',
          incidentType: alert['alert_type'] ?? 'UNKNOWN',
          incidentId: alert['incident_id'] ?? '',
        ),
      ),
    ).then((_) => _loadAlerts()); // Refresh on return
  }

  Icon _getAlertIcon(String alertType) {
    switch (alertType) {
      case 'FALL':
        return const Icon(Icons.warning, color: Colors.red, size: 32);
      case 'HIGH_FALL_RISK':
        return const Icon(Icons.info, color: Colors.orange, size: 32);
      case 'INACTIVITY':
        return const Icon(Icons.hourglass_empty, color: Colors.grey, size: 32);
      case 'PROLONGED_SLEEP':
        return const Icon(Icons.bedtime, color: Colors.purple, size: 32);
      case 'SOS_SIGNAL':
        return const Icon(Icons.sos, color: Colors.red, size: 32);
      default:
        return const Icon(Icons.notifications, color: Colors.blue, size: 32);
    }
  }

  Color _getSeverityColor(String severity) {
    switch (severity.toUpperCase()) {
      case 'CRITICAL':
        return Colors.red;
      case 'WARNING':
        return Colors.orange;
      case 'INFO':
        return Colors.blue;
      default:
        return Colors.grey;
    }
  }

  String _getTimeAgo(DateTime timestamp) {
    final now = DateTime.now();
    final difference = now.difference(timestamp);

    if (difference.inSeconds < 60) {
      return 'Just now';
    } else if (difference.inMinutes < 60) {
      return '${difference.inMinutes}m ago';
    } else if (difference.inHours < 24) {
      return '${difference.inHours}h ago';
    } else {
      return DateFormat('MMM dd, HH:mm').format(timestamp);
    }
  }

  void _showFilterMenu() {
    showModalBottomSheet(
      context: context,
      builder: (context) => Container(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              'Filter Alerts',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 16),
            ListTile(
              title: const Text('All Alerts'),
              onTap: () {
                Navigator.pop(context);
                _loadAlerts();
              },
            ),
            ListTile(
              title: const Text('Only Critical'),
              onTap: () {
                Navigator.pop(context);
                // TODO: Filter by severity
              },
            ),
            ListTile(
              title: const Text('Only Unresolved'),
              onTap: () {
                Navigator.pop(context);
                // TODO: Filter by status
              },
            ),
          ],
        ),
      ),
    );
  }
}
