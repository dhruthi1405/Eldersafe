import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../services/monitoring_api_service.dart';

class IncidentDetailsScreen extends StatefulWidget {
  final String patientId;
  final String incidentType;
  final String incidentId;

  const IncidentDetailsScreen({
    required this.patientId,
    required this.incidentType,
    required this.incidentId,
  });

  @override
  State<IncidentDetailsScreen> createState() => _IncidentDetailsScreenState();
}

class _IncidentDetailsScreenState extends State<IncidentDetailsScreen> {
  late MonitoringApiService _apiService;
  Map<String, dynamic>? _incidentData;
  bool _isLoading = true;
  String? _error;
  bool _isResolved = false;

  @override
  void initState() {
    super.initState();
    _apiService = MonitoringApiService();
    _loadIncidentDetails();
  }

  Future<void> _loadIncidentDetails() async {
    try {
      // Fetch incident data from backend
      // For now, we'll use mock data structure
      final data = {
        'incident_id': widget.incidentId,
        'patient_id': widget.patientId,
        'patient_name': 'John Doe',
        'alert_type': widget.incidentType,
        'timestamp': DateTime.now().toIso8601String(),
        'severity': _getSeverityForType(widget.incidentType),
        'confidence_score': 0.95,
        'description': 'Patient detected in prone position for extended period',
        'location': 'Living Room',
        'status': 'ACTIVE',
      };
      
      setState(() {
        _incidentData = data;
        _isLoading = false;
        _isResolved = data['status'] == 'RESOLVED';
      });
    } catch (e) {
      setState(() {
        _error = 'Failed to load incident details: $e';
        _isLoading = false;
      });
    }
  }

  String _getSeverityForType(String type) {
    switch (type) {
      case 'FALL':
        return 'CRITICAL';
      case 'HIGH_FALL_RISK':
        return 'WARNING';
      case 'INACTIVITY':
        return 'INFO';
      case 'PROLONGED_SLEEP':
        return 'WARNING';
      case 'SOS_SIGNAL':
        return 'CRITICAL';
      default:
        return 'INFO';
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('${widget.incidentType} Details'),
        centerTitle: true,
        elevation: 0,
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        Icons.error_outline,
                        size: 64,
                        color: Colors.red[300],
                      ),
                      const SizedBox(height: 16),
                      Text(
                        _error!,
                        textAlign: TextAlign.center,
                        style: const TextStyle(fontSize: 16),
                      ),
                      const SizedBox(height: 24),
                      ElevatedButton(
                        onPressed: _loadIncidentDetails,
                        child: const Text('Retry'),
                      ),
                    ],
                  ),
                )
              : _buildIncidentDetails(),
    );
  }

  Widget _buildIncidentDetails() {
    if (_incidentData == null) {
      return const Center(child: Text('No data available'));
    }

    final data = _incidentData!;
    final timestamp = DateTime.parse(data['timestamp']);
    final formattedTime = DateFormat('MMM dd, yyyy • HH:mm:ss').format(timestamp);
    final severity = data['severity'] ?? 'INFO';

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Alert Status Header
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: _getAlertColor(severity).withOpacity(0.1),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: _getAlertColor(severity),
                width: 2,
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            data['alert_type'] ?? 'Unknown Alert',
                            style: TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                              color: _getAlertColor(severity),
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            'Status: ${_isResolved ? "Resolved" : "Active"}',
                            style: TextStyle(
                              fontSize: 14,
                              color: _isResolved ? Colors.green : Colors.red,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 8,
                      ),
                      decoration: BoxDecoration(
                        color: _getAlertColor(severity),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Text(
                        severity,
                        style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.bold,
                          fontSize: 12,
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),

          const SizedBox(height: 24),

          // Patient Information Section
          _buildSection(
            title: 'Patient Information',
            children: [
              _buildInfoRow(
                icon: Icons.person,
                label: 'Patient Name',
                value: data['patient_name'] ?? 'Unknown',
              ),
              _buildInfoRow(
                icon: Icons.badge,
                label: 'Patient ID',
                value: widget.patientId,
              ),
            ],
          ),

          const SizedBox(height: 20),

          // Incident Details Section
          _buildSection(
            title: 'Incident Details',
            children: [
              _buildInfoRow(
                icon: Icons.access_time,
                label: 'Time',
                value: formattedTime,
              ),
              _buildInfoRow(
                icon: Icons.location_on,
                label: 'Location',
                value: data['location'] ?? 'Unknown',
              ),
              if (data['confidence_score'] != null)
                _buildInfoRow(
                  icon: Icons.trending_up,
                  label: 'Confidence',
                  value: '${(data['confidence_score'] * 100).toStringAsFixed(1)}%',
                ),
            ],
          ),

          const SizedBox(height: 20),

          // Description Section
          if (data['description'] != null) ...[
            _buildSection(
              title: 'Description',
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.grey[100],
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    data['description'],
                    style: const TextStyle(fontSize: 14),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
          ],

          // Action Buttons
          if (!_isResolved)
            Column(
              children: [
                SizedBox(
                  width: double.infinity,
                  height: 50,
                  child: ElevatedButton.icon(
                    onPressed: _markAsResolved,
                    icon: const Icon(Icons.check_circle),
                    label: const Text('Mark as Resolved'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.green,
                      foregroundColor: Colors.white,
                    ),
                  ),
                ),
                const SizedBox(height: 12),
              ],
            ),

          SizedBox(
            width: double.infinity,
            height: 50,
            child: OutlinedButton.icon(
              onPressed: _contactCareTeam,
              icon: const Icon(Icons.phone),
              label: const Text('Contact Care Team'),
            ),
          ),

          const SizedBox(height: 12),

          SizedBox(
            width: double.infinity,
            height: 50,
            child: OutlinedButton.icon(
              onPressed: _viewVideoRecording,
              icon: const Icon(Icons.video_camera_back),
              label: const Text('View Video Recording'),
            ),
          ),

          const SizedBox(height: 24),
        ],
      ),
    );
  }

  Widget _buildSection({
    required String title,
    required List<Widget> children,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.bold,
            color: Colors.black87,
          ),
        ),
        const SizedBox(height: 12),
        ...children,
      ],
    );
  }

  Widget _buildInfoRow({
    required IconData icon,
    required String label,
    required String value,
  }) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: Colors.blue, size: 20),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: const TextStyle(
                    fontSize: 12,
                    color: Colors.grey,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  value,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                    color: Colors.black87,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Color _getAlertColor(String severity) {
    switch (severity) {
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

  Future<void> _markAsResolved() async {
    try {
      // Call backend API to mark as resolved
      // await _apiService.markIncidentResolved(widget.incidentId);
      
      setState(() {
        _isResolved = true;
      });

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('✓ Incident marked as resolved'),
          backgroundColor: Colors.green,
        ),
      );

      // Go back after a short delay
      await Future.delayed(const Duration(seconds: 2));
      if (mounted) {
        Navigator.pop(context);
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error: $e'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  Future<void> _contactCareTeam() async {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Contact Care Team'),
        content: const Text('Select how you want to contact the care team:'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              _makePhoneCall();
            },
            child: const Text('Call'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              _sendMessage();
            },
            child: const Text('Message'),
          ),
        ],
      ),
    );
  }

  void _makePhoneCall() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Calling care team...')),
    );
  }

  void _sendMessage() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Opening messaging app...')),
    );
  }

  void _viewVideoRecording() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Loading video recording...')),
    );
    // Navigate to video player screen
  }
}
