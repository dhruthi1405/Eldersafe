import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';
import '../models/user.dart';
import '../models/elder.dart';
import '../models/alert.dart';
import '../services/auth_service.dart';
import '../services/firestore_service.dart';
import '../services/monitoring_api_service.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({Key? key}) : super(key: key);

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  late final FirestoreService _firestoreService;
  late final AuthService _authService;
  late final MonitoringApiService _monitoringApiService;
  AppUser? _currentUser;
  List<Elder> _elders = [];
  List<AppAlert> _recentAlerts = [];
  List<Map<String, dynamic>> _backendPatients = [];
  bool _isLoading = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _firestoreService = FirestoreService();
    _authService = AuthService();
    _monitoringApiService = MonitoringApiService(authService: _authService);
    _loadUserData();
  }

  Future<void> _loadUserData() async {
    try {
      final userId = _authService.currentUser?.uid;
      if (userId == null) throw Exception('User not authenticated');

      // Load user document
      AppUser? user;
      try {
        user = await _firestoreService.getUser(userId);
      } catch (e) {
        debugPrint('Firestore user profile unavailable: $e');
      }

      final firebaseUser = FirebaseAuth.instance.currentUser;
      user ??= AppUser(
        userId: userId,
        email: firebaseUser?.email ?? '',
        name: firebaseUser?.displayName ?? 'Caregiver',
        role: 'CAREGIVER',
        createdAt: DateTime.now(),
      );

      setState(() => _currentUser = user);

      try {
        await _monitoringApiService.syncFirebaseUser(
          role: user.role.toLowerCase() == 'doctor' ? 'doctor' : 'caretaker',
        );
        final summary = await _monitoringApiService.fetchMonitoringSummary();
        final backendPatients = List<Map<String, dynamic>>.from(summary['patients'] ?? const []);
        final backendAlerts = List<Map<String, dynamic>>.from(summary['recent_alerts'] ?? const []);

        setState(() {
          _backendPatients = backendPatients;
          _recentAlerts = backendAlerts.map((alert) {
            return AppAlert(
              alertId: (alert['id'] ?? '').toString(),
              elderId: (alert['patient_id'] ?? '').toString(),
              alertType: (alert['alert_type'] ?? 'ACTIVITY').toString(),
              activityLabel: (alert['alert_type'] ?? '').toString().toLowerCase(),
              confidence: ((alert['confidence'] ?? 0.0) as num).toDouble(),
              message: (alert['message'] ?? '').toString(),
              timestamp: DateTime.tryParse((alert['notified_at'] ?? '').toString()) ?? DateTime.now(),
              acknowledged: (alert['resolved'] ?? false) == true,
            );
          }).toList();
        });
      } catch (e) {
        debugPrint('Backend monitoring unavailable, using Firestore only: $e');
      }

      // Load elders if caregiver
      if (user.role == 'CAREGIVER') {
        try {
          final elders = await _firestoreService.getEldersForCaregiver(userId);
          setState(() => _elders = elders);

          // Load recent alerts from first elder (if elderId exists)
          if (_recentAlerts.isEmpty && elders.isNotEmpty && elders.first.elderId.isNotEmpty) {
            final alerts =
                await _firestoreService.getAlertsForElder(elders.first.elderId, limit: 5);
            setState(() => _recentAlerts = alerts);
          }
        } catch (e) {
          debugPrint('Firestore elder/alert data unavailable: $e');
        }
      }

      setState(() => _isLoading = false);
    } catch (e) {
      setState(() {
        _errorMessage = e.toString();
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return Scaffold(
        appBar: AppBar(
          title: const Text('ElderCare AI'),
          elevation: 0,
        ),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('ElderCare AI'),
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            onPressed: () {
              Navigator.of(context).pushNamed('/settings');
            },
          ),
        ],
      ),
      body: _errorMessage != null
          ? _buildErrorWidget()
          : _currentUser?.role == 'CAREGIVER'
              ? _buildCaregiverView()
              : _buildElderView(),
    );
  }

  Widget _buildErrorWidget() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.error_outline, size: 64, color: Colors.red[300]),
          const SizedBox(height: 16),
          Text('Error loading data:\n$_errorMessage'),
          const SizedBox(height: 24),
          ElevatedButton(
            onPressed: _loadUserData,
            child: const Text('Retry'),
          ),
        ],
      ),
    );
  }

  // CAREGIVER VIEW
  Widget _buildCaregiverView() {
    return RefreshIndicator(
      onRefresh: _loadUserData,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // User greeting card
              _buildUserCard(),
              const SizedBox(height: 24),

              // Elders section
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    '👴 Elders You\'re Monitoring',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  ElevatedButton.icon(
                    onPressed: () {
                      Navigator.of(context).pushNamed('/add-elder');
                    },
                    icon: const Icon(Icons.add),
                    label: const Text('Add'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.blue,
                      foregroundColor: Colors.white,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),

              if (_elders.isEmpty)
                (_backendPatients.isNotEmpty
                    ? Column(
                        children: _backendPatients
                            .map((patient) => _buildBackendPatientCard(patient))
                            .toList(),
                      )
                    : _buildEmptyState(
                        icon: Icons.person_outline,
                        title: 'No elders added yet',
                        subtitle: 'Tap "Add" to start monitoring someone',
                      ))
              else
                ..._elders.map((elder) => _buildElderCard(elder)).toList(),

              const SizedBox(height: 24),

              // Video monitoring section
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: () {
                    Navigator.of(context).pushNamed('/video-streaming');
                  },
                  icon: const Icon(Icons.videocam),
                  label: const Text('📹 Live Video Monitoring'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.purple,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 12),
                  ),
                ),
              ),

              const SizedBox(height: 24),

              // Recent alerts section
              if (_recentAlerts.isNotEmpty) ...[
                const Text(
                  '🚨 Recent Alerts',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 12),
                ..._recentAlerts.map((alert) => _buildAlertCard(alert)).toList(),
                const SizedBox(height: 16),
              ],
            ],
          ),
        ),
      ),
    );
  }

  // ELDER VIEW
  Widget _buildElderView() {
    return SingleChildScrollView(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // User greeting card
            _buildUserCard(),
            const SizedBox(height: 24),

            // Info box
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.blue[50],
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.blue[200]!),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    '👋 Welcome to ElderCare!',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Your activity is being monitored. If you fall or need help, we\'ll alert your caregivers immediately.',
                    style: TextStyle(
                      fontSize: 14,
                      color: Colors.blue[800],
                      height: 1.5,
                    ),
                  ),
                  const SizedBox(height: 16),
                  ElevatedButton.icon(
                    onPressed: _showSOSAlert,
                    icon: const Icon(Icons.emergency),
                    label: const Text('Send SOS Alert'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.red,
                      foregroundColor: Colors.white,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),

            // Activity tips
            const Text(
              '💡 Tips for Safety',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            _buildTipCard(Icons.directions_walk, 'Stay Active',
                'Regular movement helps prevent muscle weakness'),
            _buildTipCard(Icons.bedtime, 'Get Rest',
                'Adequate sleep is important for your health'),
            _buildTipCard(Icons.water_drop, 'Stay Hydrated',
                'Drink water regularly throughout the day'),
          ],
        ),
      ),
    );
  }

  Widget _buildUserCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [Colors.blue[400]!, Colors.blue[600]!],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.blue.withOpacity(0.3),
            blurRadius: 8,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Hello, ${_currentUser?.name ?? "User"}! 👋',
            style: const TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.bold,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Icon(
                _currentUser?.role == 'CAREGIVER'
                    ? Icons.support_agent
                    : Icons.person,
                color: Colors.white70,
                size: 16,
              ),
              const SizedBox(width: 8),
              Text(
                '${_currentUser?.role == 'CAREGIVER' ? 'Caregiver' : 'Elder'} • ${_currentUser?.email}',
                style: const TextStyle(
                  fontSize: 14,
                  color: Colors.white70,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildElderCard(Elder elder) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        border: Border.all(color: Colors.grey[300]!),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    elder.name,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '${elder.age} years old • ${elder.gender}',
                    style: TextStyle(
                      fontSize: 14,
                      color: Colors.grey[600],
                    ),
                  ),
                ],
              ),
              PopupMenuButton(
                itemBuilder: (context) => [
                  const PopupMenuItem(
                    value: 'view',
                    child: Row(
                      children: [
                        Icon(Icons.visibility),
                        SizedBox(width: 8),
                        Text('View Details'),
                      ],
                    ),
                  ),
                  const PopupMenuItem(
                    value: 'edit',
                    child: Row(
                      children: [
                        Icon(Icons.edit),
                        SizedBox(width: 8),
                        Text('Edit'),
                      ],
                    ),
                  ),
                ],
              ),
            ],
          ),
          if (elder.medicalConditions.isNotEmpty) ...[
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              children: elder.medicalConditions
                  .map(
                    (condition) => Chip(
                      label: Text(condition),
                      backgroundColor: Colors.red[100],
                      labelStyle: TextStyle(color: Colors.red[700]),
                    ),
                  )
                  .toList(),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildAlertCard(AppAlert alert) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        border: Border.all(color: alert.color),
        borderRadius: BorderRadius.circular(8),
        color: alert.color.withOpacity(0.1),
      ),
      child: Row(
        children: [
          Icon(alert.icon, color: alert.color, size: 24),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  alert.alertType,
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: alert.color,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  alert.message,
                  style: const TextStyle(fontSize: 13),
                ),
                const SizedBox(height: 4),
                Text(
                  '${alert.timestamp.hour}:${alert.timestamp.minute.toString().padLeft(2, '0')}',
                  style: TextStyle(fontSize: 12, color: Colors.grey[600]),
                ),
              ],
            ),
          ),
          if (!alert.acknowledged)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: Colors.orange,
                borderRadius: BorderRadius.circular(4),
              ),
              child: const Text(
                'NEW',
                style: TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.bold,
                  color: Colors.white,
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildBackendPatientCard(Map<String, dynamic> patient) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        border: Border.all(color: Colors.blue[200]!),
        borderRadius: BorderRadius.circular(12),
        color: Colors.blue.withOpacity(0.04),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            patient['full_name']?.toString() ?? 'Unknown Patient',
            style: const TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'Patient ID: ${patient['patient_id'] ?? '-'}',
            style: TextStyle(color: Colors.grey[700]),
          ),
          if ((patient['emergency_contact'] ?? '').toString().isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              'Emergency Contact: ${patient['emergency_contact']} (${patient['emergency_phone'] ?? '-'})',
              style: TextStyle(color: Colors.grey[700]),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildEmptyState({
    required IconData icon,
    required String title,
    required String subtitle,
  }) {
    return Container(
      padding: const EdgeInsets.all(32),
      child: Column(
        children: [
          Icon(icon, size: 64, color: Colors.grey[300]),
          const SizedBox(height: 16),
          Text(
            title,
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
              color: Colors.grey[700],
            ),
          ),
          const SizedBox(height: 8),
          Text(
            subtitle,
            style: TextStyle(
              fontSize: 14,
              color: Colors.grey[500],
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  Widget _buildTipCard(IconData icon, String title, String description) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        border: Border.all(color: Colors.grey[200]!),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Icon(icon, color: Colors.blue, size: 24),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 14,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  description,
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.grey[600],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  void _showSOSAlert() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Send SOS Alert?'),
        content: const Text(
          'This will notify your caregivers that you need immediate help.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('✓ SOS alert sent to your caregivers!'),
                  backgroundColor: Colors.red,
                ),
              );
              // TODO: Implement actual SOS alert
            },
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Send SOS'),
          ),
        ],
      ),
    );
  }
}
