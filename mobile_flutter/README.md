# Cassidy AI - Flutter Mobile App

A cross-platform mobile application built with Flutter for the Cassidy AI journaling platform.

## Features

- **Cross-Platform**: Runs on both iOS and Android
- **Authentication**: Login and registration with JWT tokens
- **Chat Interface**: Real-time chat with Cassidy AI using DashChat
- **Session Management**: Create and manage chat sessions
- **Material Design**: Beautiful, responsive UI following Material Design principles
- **State Management**: Provider pattern for efficient state management

## Prerequisites

- Flutter SDK 3.0+
- Dart SDK 3.0+
- iOS development: Xcode 15+ (for iOS builds)
- Android development: Android Studio (for Android builds)

## Setup

1. **Install dependencies:**
   ```bash
   flutter pub get
   ```

2. **Run the app:**
   ```bash
   # iOS Simulator
   flutter run

   # Android Emulator
   flutter run

   # Specific device
   flutter devices  # List available devices
   flutter run -d <device_id>
   ```

## Project Structure

```
lib/
├── main.dart              # App entry point and routing
├── models/
│   └── api_models.dart    # Data models for API communication
├── services/
│   ├── api_service.dart   # HTTP client for backend API
│   ├── auth_service.dart  # Authentication state management
│   └── storage_service.dart # Local storage (SharedPreferences)
└── screens/
    ├── loading_screen.dart # Loading/splash screen
    ├── login_screen.dart  # Authentication screen
    └── chat_screen.dart   # Main chat interface
```

## Architecture

- **State Management**: Provider pattern with ChangeNotifier
- **Navigation**: GoRouter for declarative routing
- **HTTP Client**: Dio for API communication
- **Local Storage**: SharedPreferences for token storage
- **Chat UI**: DashChat for message interface

## Backend Integration

The app integrates with the Cassidy backend API:

- **Base URL**: `https://tq68ditf6b.execute-api.us-east-1.amazonaws.com/prod/api/v1`
- **Authentication**: JWT Bearer tokens
- **Default Credentials**: `user_123` / `1234`
- **Endpoints**:
  - `POST /auth/login` - User authentication
  - `POST /auth/register` - User registration
  - `GET /auth/me` - Get current user profile
  - `POST /sessions` - Create chat session
  - `POST /agent/chat/{session_id}` - Send message to AI

## Testing

Run tests with:
```bash
flutter test
```

## Building for Production

### iOS
```bash
flutter build ios --release
```

### Android
```bash
flutter build apk --release
# or
flutter build appbundle --release
```

## Development Notes

- **Hot Reload**: Press `r` in terminal for hot reload during development
- **Debug Logging**: Console logs are enabled for debugging API interactions
- **Error Handling**: Comprehensive error handling with user-friendly messages

## Dependencies

Key dependencies used:
- `provider` - State management
- `go_router` - Navigation
- `dio` - HTTP client
- `shared_preferences` - Local storage
- `dash_chat_2` - Chat UI components
- `material_design_icons_flutter` - Material Design icons

## Troubleshooting

### iOS Issues
- Ensure Xcode is installed and up to date
- Run `flutter doctor` to check for iOS setup issues
- For simulator issues, try `flutter clean && flutter pub get`

### Android Issues
- Ensure Android Studio and SDK are installed
- Check that an emulator is running or device is connected
- Run `flutter doctor` to diagnose Android setup issues

### Network Issues
- Check that the backend API is accessible
- Verify network permissions in iOS simulator settings