import 'package:flutter/foundation.dart' show kIsWeb, defaultTargetPlatform, TargetPlatform;
import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'firebase_options.dart';
import 'screens/home_screen.dart';
import 'screens/activity_tracking_screen.dart';
import 'screens/alerts_screen.dart';
import 'screens/auth/login_screen.dart';
import 'screens/auth/signup_screen.dart';
import 'screens/auth/role_selection_screen.dart';
import 'screens/auth/elder_profile_setup_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/add_elder_screen.dart';
import 'screens/video_streaming_screen.dart';
import 'screens/video_library_screen.dart';
import 'services/auth_service.dart';
import 'services/monitoring_api_service.dart';
import 'services/notification_service.dart';

// Background message handler (must be a top-level function)
Future<void> _firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  print('Handling a background message: ${message.messageId}');
  print('Background message data: ${message.data}');
}

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize Firebase
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );

  // Disable reCAPTCHA for testing
  await AuthService.disableRecaptchaForTesting();

  // Set background message handler
  FirebaseMessaging.onBackgroundMessage(_firebaseMessagingBackgroundHandler);

  runApp(const MyApp());
}

class MyApp extends StatefulWidget {
  const MyApp({Key? key}) : super(key: key);

  @override
  State<MyApp> createState() => _MyAppState();
}

class _MyAppState extends State<MyApp> {
  final _authService = AuthService();
  late final MonitoringApiService _monitoringApiService;
  final GlobalKey<NavigatorState> _navigatorKey = GlobalKey<NavigatorState>();

  @override
  void initState() {
    super.initState();
    _monitoringApiService = MonitoringApiService(authService: _authService);
    
    // Initialize notification service
    NotificationService().initialize(navKey: _navigatorKey);
    
    _initializeFirebaseMessaging();
    _authService.authStateChanges.listen((user) async {
      if (user == null) return;
      try {
        await _monitoringApiService.syncFirebaseUser();
        final token = await FirebaseMessaging.instance.getToken();
        if (token != null && token.isNotEmpty) {
          await _monitoringApiService.registerDeviceToken(
            deviceToken: token,
            platform: _detectPlatform(),
          );
        }
      } catch (e) {
        print('Backend sync skipped: $e');
      }
    });
  }

  Future<void> _initializeFirebaseMessaging() async {
    final messaging = FirebaseMessaging.instance;

    // Request notification permissions
    final settings = await messaging.requestPermission(
      alert: true,
      announcement: true,
      badge: true,
      carPlay: true,
      criticalAlert: true,
      provisional: true,
      sound: true,
    );

    print('Notification permissions: ${settings.authorizationStatus}');
    await _registerCurrentDeviceToken();

    // Get initial message if opened from notification
    final initialMessage = await messaging.getInitialMessage();
    if (initialMessage != null) {
      _handleMessage(initialMessage);
    }

    // Listen for foreground messages
    FirebaseMessaging.onMessage.listen((message) {
      print('Got a message whilst in foreground!');
      print('Message data: ${message.data}');
      _handleMessage(message);
    });

    // Listen for messages when app is opened from background
    FirebaseMessaging.onMessageOpenedApp.listen((message) {
      print('Message opened from background: ${message.notification?.title}');
      _handleMessage(message);
    });

    FirebaseMessaging.instance.onTokenRefresh.listen((token) async {
      try {
        await _monitoringApiService.registerDeviceToken(
          deviceToken: token,
          platform: _detectPlatform(),
        );
      } catch (e) {
        print('Token refresh sync skipped: $e');
      }
    });
  }

  Future<void> _registerCurrentDeviceToken() async {
    final user = _authService.currentUser;
    if (user == null) return;

    try {
      await _monitoringApiService.syncFirebaseUser();
      final token = await FirebaseMessaging.instance.getToken();
      if (token != null && token.isNotEmpty) {
        await _monitoringApiService.registerDeviceToken(
          deviceToken: token,
          platform: _detectPlatform(),
        );
      }
    } catch (e) {
      print('Initial device registration skipped: $e');
    }
  }

  String _detectPlatform() {
    if (kIsWeb) return 'web';
    switch (defaultTargetPlatform) {
      case TargetPlatform.android:
        return 'android';
      case TargetPlatform.iOS:
        return 'ios';
      case TargetPlatform.macOS:
        return 'macos';
      case TargetPlatform.windows:
        return 'windows';
      case TargetPlatform.linux:
        return 'linux';
      default:
        return 'mobile';
    }
  }

  void _handleMessage(RemoteMessage message) {
    print('═════════════════════════════════════');
    print('📨 ALERT RECEIVED');
    print('═════════════════════════════════════');
    print('Title: ${message.notification?.title}');
    print('Body: ${message.notification?.body}');
    print('Data: ${message.data}');
    print('═════════════════════════════════════');

    // Show notification even if app is in foreground
    if (message.notification != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            '${message.notification!.title}\n${message.notification!.body}',
          ),
          duration: const Duration(seconds: 5),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'ElderCare AI Monitoring',
      theme: ThemeData(
        primarySwatch: Colors.blue,
        useMaterial3: true,
        brightness: Brightness.light,
      ),
      darkTheme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
      ),
      themeMode: ThemeMode.system,
      debugShowCheckedModeBanner: false,
      navigatorKey: _navigatorKey,
      home: StreamBuilder<User?>(
        stream: _authService.authStateChanges,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Scaffold(
              body: Center(
                child: CircularProgressIndicator(),
              ),
            );
          }

          // User is logged in
          if (snapshot.hasData) {
            return const MainAppContainer();
          }

          // User is not logged in
          return const LoginScreen();
        },
      ),
      routes: {
        '/login': (context) => const LoginScreen(),
        '/signup': (context) => const SignupScreen(),
        '/role-selection': (context) => const RoleSelectionScreen(),
        '/elder-profile-setup': (context) => const ElderProfileSetupScreen(),
        '/home': (context) => const MainAppContainer(),
        '/settings': (context) => const SettingsScreen(),
        '/add-elder': (context) => const AddElderScreen(),
        '/video-streaming': (context) => const VideoStreamingScreen(),
        '/video-library': (context) => const VideoLibraryScreen(),
      },
    );
  }
}

class MainAppContainer extends StatefulWidget {
  const MainAppContainer({Key? key}) : super(key: key);

  @override
  State<MainAppContainer> createState() => _MainAppContainerState();
}

class _MainAppContainerState extends State<MainAppContainer> {
  int _currentTab = 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _currentTab,
        children: const [
          HomeScreen(),
          VideoLibraryScreen(),
          ActivityTrackingScreen(),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentTab,
        onDestinationSelected: (index) {
          setState(() {
            _currentTab = index;
          });
        },
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.notifications_outlined),
            selectedIcon: Icon(Icons.notifications),
            label: 'Alerts',
          ),
          NavigationDestination(
            icon: Icon(Icons.videocam_outlined),
            selectedIcon: Icon(Icons.videocam),
            label: 'Videos',
          ),
          NavigationDestination(
            icon: Icon(Icons.timeline_outlined),
            selectedIcon: Icon(Icons.timeline),
            label: 'Activities',
          ),
        ],
      ),
    );
  }
}
