import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../services/auth_service.dart';
import '../services/firestore_service.dart';

class VideoStreamingScreen extends StatefulWidget {
  const VideoStreamingScreen({Key? key}) : super(key: key);

  @override
  State<VideoStreamingScreen> createState() => _VideoStreamingScreenState();
}

class _VideoStreamingScreenState extends State<VideoStreamingScreen> {
  late WebViewController _webViewController;
  late FirestoreService _firestoreService;
  late AuthService _authService;

  String _flaskServerUrl = 'http://10.110.185.106:5000';
  String _systemStatus = 'Connecting...';
  String _fallDetection = 'Not Detected';
  String _confidence = '0%';
  String _activity = 'Standing';
  bool _isConnected = false;

  @override
  void initState() {
    super.initState();
    _firestoreService = FirestoreService();
    _authService = AuthService();
    _initializeWebView();
    _checkHealthAndStream();
  }

  void _initializeWebView() {
    _webViewController = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..loadRequest(Uri.parse('$_flaskServerUrl/video_feed'));
  }

  Future<void> _checkHealthAndStream() async {
    try {
      // Check server health
      final response = await http.get(
        Uri.parse('$_flaskServerUrl/health'),
        headers: {'Content-Type': 'application/json'},
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        setState(() {
          _isConnected = true;
          _systemStatus = data['firebase'] == 'connected' ? '● Healthy' : '● Firebase Disconnected';
        });
      }
    } catch (e) {
      setState(() {
        _isConnected = false;
        _systemStatus = '● Offline';
      });
      if (mounted) {
        _showConnectionError();
      }
    }
  }

  Future<void> _triggerAlert(String alertType) async {
    final userId = _authService.currentUser?.uid;
    if (userId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('User not authenticated')),
      );
      return;
    }

    try {
      final response = await http.post(
        Uri.parse('$_flaskServerUrl/api/alert'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'elder_id': userId,
          'alert_type': alertType,
          'confidence': alertType == 'FALL' ? 0.92 : 1.0,
          'message': alertType == 'FALL'
              ? 'Fall detected - activating alert'
              : 'Manual SOS alert activated',
        }),
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Alert sent to: ${data['recipient']}'),
            backgroundColor: Colors.green,
          ),
        );

        setState(() {
          if (alertType == 'FALL') {
            _fallDetection = '🚨 Detected';
            _confidence = '92%';
          }
        });
      } else {
        throw Exception('Failed to send alert');
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: ${e.toString()}')),
      );
    }
  }

  void _showConnectionError() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Connection Error'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Unable to connect to Flask server. Make sure:',
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            const Text('1. Flask server is running (python flask_server.py)'),
            const SizedBox(height: 8),
            RichText(
              text: TextSpan(
                text: '2. Flask server IP is: ',
                style: const TextStyle(color: Colors.black),
                children: [
                  TextSpan(
                    text: _flaskServerUrl,
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      color: Colors.blue,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              '3. Both devices are on same WiFi network',
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('OK'),
          ),
          TextButton(
            onPressed: () {
              _showServerConfigDialog();
              Navigator.pop(context);
            },
            child: const Text('Change Server IP'),
          ),
        ],
      ),
    );
  }

  void _showServerConfigDialog() {
    final controller = TextEditingController(text: _flaskServerUrl);
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Flask Server Configuration'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('Enter Flask server URL:'),
            const SizedBox(height: 12),
            TextField(
              controller: controller,
              decoration: InputDecoration(
                hintText: 'e.g., http://192.168.1.100:5000',
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
            ),
            const SizedBox(height: 12),
            const Text(
              'Find your Flask server IP:\n'
              '1. Run Flask server on your computer\n'
              '2. Check console for server address\n'
              '3. Get your computer IP: ipconfig (Windows) or ifconfig (Mac/Linux)',
              style: TextStyle(fontSize: 12, color: Colors.grey),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () {
              setState(() {
                _flaskServerUrl = controller.text;
              });
              _initializeWebView();
              _checkHealthAndStream();
              Navigator.pop(context);
            },
            child: const Text('Save'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('📹 Video Monitoring'),
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: _showServerConfigDialog,
          ),
        ],
      ),
      body: Column(
        children: [
          // Status Bar
          Container(
            padding: const EdgeInsets.all(12),
            color: _isConnected ? Colors.blue[50] : Colors.red[50],
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _buildStatusItem('System', _systemStatus),
                _buildStatusItem('Fall', _fallDetection),
                _buildStatusItem('Confidence', _confidence),
                _buildStatusItem('Activity', _activity),
              ],
            ),
          ),

          // Video Feed
          Expanded(
            child: Container(
              color: Colors.black,
              child: _isConnected
                  ? WebViewWidget(controller: _webViewController)
                  : Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(
                            Icons.cloud_off,
                            size: 64,
                            color: Colors.white,
                          ),
                          const SizedBox(height: 16),
                          const Text(
                            'Server Offline',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            _flaskServerUrl,
                            style: const TextStyle(
                              color: Colors.grey,
                              fontSize: 12,
                            ),
                          ),
                          const SizedBox(height: 24),
                          ElevatedButton.icon(
                            onPressed: _checkHealthAndStream,
                            icon: const Icon(Icons.refresh),
                            label: const Text('Retry'),
                          ),
                          const SizedBox(height: 8),
                          ElevatedButton.icon(
                            onPressed: _showServerConfigDialog,
                            icon: const Icon(Icons.settings),
                            label: const Text('Change Server'),
                          ),
                        ],
                      ),
                    ),
            ),
          ),

          // Controls
          Container(
            padding: const EdgeInsets.all(16),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                ElevatedButton.icon(
                  onPressed: _isConnected ? () => _triggerAlert('FALL') : null,
                  icon: const Icon(Icons.warning_amber),
                  label: const Text('Test Fall'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.blue,
                    foregroundColor: Colors.white,
                  ),
                ),
                const SizedBox(width: 12),
                ElevatedButton.icon(
                  onPressed: _isConnected ? () => _triggerAlert('SOS') : null,
                  icon: const Icon(Icons.emergency),
                  label: const Text('Send SOS'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.red,
                    foregroundColor: Colors.white,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatusItem(String label, String value) {
    return Column(
      children: [
        Text(
          label,
          style: const TextStyle(
            fontSize: 11,
            color: Colors.grey,
            fontWeight: FontWeight.w500,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          value,
          style: TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.bold,
            color: value.contains('●') && value.contains('Healthy')
                ? Colors.green
                : value.contains('●') && value.contains('Offline')
                    ? Colors.red
                    : Colors.black,
          ),
        ),
      ],
    );
  }

  @override
  void dispose() {
    super.dispose();
  }
}
