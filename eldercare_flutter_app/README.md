# ElderCare AI Mobile App

> Real-time fall detection and activity monitoring with instant push notifications

Cross-platform mobile app (iOS & Android) for receiving instant alerts from ElderCare AI monitoring system.

## ✨ Features

- 📱 **Real-time Notifications** — Get alerts within 1 second
- 🔔 **Rich Alerts** — Fall detection, SOS signals, activity labels
- 📊 **Alert History** — View all past alerts in chronological order
- 📋 **Copy Token** — One-tap device token copy for configuration
- 🌓 **Dark Theme** — Auto-switches based on device settings
- 💾 **Local Storage** — Alerts persist even after app restart
- 🔄 **Background Support** — Receives notifications even when app is closed

## 🚀 Quick Start

### Installation

1. **Install Flutter:**
   ```bash
   # https://flutter.dev/docs/get-started/install
   flutter --version
   ```

2. **Setup Project:**
   ```bash
   cd eldercare_flutter_app
   flutter pub get
   ```

3. **Configure Firebase:**
   ```bash
   dart pub global activate flutterfire_cli
   flutterfire configure
   ```

4. **Run App:**
   ```bash
   flutter run
   ```

### Getting Your Device Token

1. Run the app on your phone
2. Device token appears on screen and console
3. Tap "Copy Token" button
4. Set environment variable:
   ```bash
   export FCM_DEVICE_TOKEN=your_token_here
   ```

## 📋 Requirements

- **Flutter SDK**: 3.0.0+
- **Android**: 5.0+ (API 21)
- **iOS**: 11.0+
- **Firebase Project**: With Cloud Messaging enabled

## 🏗️ Architecture

```
Flutter App
  ├── Firebase Messaging (FCM)
  │   └── Cloud Messaging Service
  ├── Home Screen UI
  │   ├── Device Token Card
  │   ├── Status Indicator
  │   └── Alert History List
  └── Storage
      └── SharedPreferences (local alerts)
```

## 📁 File Structure

```
lib/
├── main.dart                    # App entry point & Firebase init
├── firebase_options.dart        # Auto-generated Firebase config
└── screens/
    └── home_screen.dart         # Main UI screen
```

## Dependencies

- **firebase_core**: ^2.27.0 — Firebase SDK
- **firebase_messaging**: ^14.7.0 — Push notifications
- **provider**: ^6.1.0 — State management
- **shared_preferences**: ^2.2.2 — Local storage
- **intl**: ^0.19.0 — Internationalization

See `pubspec.yaml` for complete list.

## Alert Types

| Type | Icon | Color | Meaning |
|------|------|-------|---------|
| Fall | 🚨 | Red | Person detected falling |
| SOS Wave | 🆘 | Orange | Emergency signal detected |
| Sleep Alert | 😴 | Purple | Prolonged sleep detected |
| Inactivity | ⚠️ | Gray | No movement for extended time |
| Fall Risk | ⚠️ | Amber | High gait fall risk detected |

## 🔐 Security

- Device token is only used for this app instance
- No personal data transmitted beyond alert metadata
- Notifications sent through Firebase secure channels
- Device token can be revoked and regenerated anytime

## Testing

### Test Receiving Alerts

1. **Start app:**
   ```bash
   flutter run
   ```

2. **Copy device token from console**

3. **Run inference with token:**
   ```bash
   export FCM_DEVICE_TOKEN=your_token
   python pipeline/inference.py \
     --source test_video.mp4 \
     --enable_firebase
   ```

4. **Check phone for notification**

## Troubleshooting

### App won't run
```bash
flutter clean
flutter pub get
flutter run -v
```

### No notifications received
- Check notification permissions on phone
- Check phone has internet connection
- Verify device token is correct
- Check Firebase Console for delivery status

### Missing Firebase config
```bash
flutterfire configure
```

### Specific to Android
- Ensure minSdkVersion is 21 in `android/app/build.gradle`
- Download `google-services.json` from Firebase Console
- Place in `android/app/google-services.json`

### Specific to iOS
- Download `GoogleService-Info.plist` from Firebase Console
- Add to Xcode project (Runner)
- Uncomment platform line in `ios/Podfile`
- Run: `cd ios && pod install && cd ..`

## 📚 Documentation

- [QUICK_START.md](QUICK_START.md) — 5-minute setup
- [FLUTTER_SETUP.md](FLUTTER_SETUP.md) — Detailed instructions
- [Firebase Setup](../FIREBASE_SETUP_GUIDE.md) — Server configuration

## 🎯 Usage

### Production Build (Android)
```bash
flutter build apk --release
# Output: build/app/outputs/flutter-apk/app-release.apk
```

### Production Build (iOS)
```bash
flutter build ios --release
# Output: build/ios/iphoneos/Runner.app
```

### Distribution

1. **Play Store** (Android)
   - Build APK or build bundle
   - Upload to Google Play Console

2. **App Store** (iOS)
   - Build IPA using Xcode
   - Upload to App Store Connect

## 🤝 Contributing

To modify the app:

1. Update code in `lib/`
2. Test: `flutter run`
3. Build: `flutter build apk --release`

## 📞 Support

If notifications aren't working:

1. Run setup verification: `python test_firebase_setup.py`
2. Check Firebase Console for delivery logs
3. Review console output for `[Firebase]` messages
4. Check device token is correctly set

## 📄 License

© 2026 ElderCare AI System. All rights reserved.

## Version

- **App Version**: 1.0.0
- **Build**: 1
- **Firebase SDK**: 2.27.0+
- **Flutter**: 3.0.0+

---

**Status**: ✅ Production Ready  
**Last Updated**: April 15, 2026  
**Platform Support**: iOS 11.0+, Android 5.0+
