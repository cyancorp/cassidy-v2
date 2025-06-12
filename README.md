# Cassidy AI Journaling Assistant

A comprehensive AI-powered journaling platform with web and mobile applications, powered by pydantic-ai and Anthropic's Claude.

## Project Structure

This is a monorepo containing all components of the Cassidy platform:

```
cassidy-claudecode/
├── backend/           # FastAPI backend with pydantic-ai agent
├── frontend/          # React web application
├── mobile_flutter/   # Flutter mobile app (iOS & Android)
└── infrastructure/   # AWS CDK deployment configuration
```

## Features

- **AI-Powered Journaling**: Intelligent journaling assistant using Claude
- **Multi-Platform**: Web and mobile applications with consistent UX
- **Structured Journaling**: Automatic structuring of journal entries
- **User Preferences**: Personalized AI responses based on user goals
- **Secure Authentication**: JWT-based authentication system
- **Cloud Deployment**: Serverless deployment on AWS Lambda

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 16+
- Flutter SDK 3.0+
- Docker (for deployment)
- AWS CLI (for deployment)
- Xcode (for iOS development)
- Android Studio (for Android development)

### Backend Development

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend Development

```bash
cd frontend
npm install
npm run dev
```

### Mobile Development (Flutter)

```bash
cd mobile_flutter
flutter pub get

# iOS
flutter run

# Android (requires Android emulator or device)
flutter run

# Web (for testing)
flutter run -d web
```

## Documentation

- [Backend Documentation](./backend/README.md)
- [Mobile App Documentation](./mobile_flutter/README.md)
- [Deployment Guide](./infrastructure/README.md)

## Testing

### Backend Tests
```bash
cd backend
pytest
```

### Frontend Tests
```bash
cd frontend
npm test
```

### Mobile Tests (Flutter)
```bash
cd mobile_flutter
flutter test
```

## Deployment

The application is deployed using AWS Lambda and API Gateway:

```bash
cd infrastructure
cdk deploy --require-approval never
```

## Architecture

- **Backend**: FastAPI + pydantic-ai + SQLAlchemy
- **Frontend**: React + TypeScript + Vite
- **Mobile**: Flutter + Dart
- **AI**: Anthropic Claude via pydantic-ai
- **Database**: SQLite (local) / PostgreSQL (production)
- **Deployment**: AWS Lambda + API Gateway + CDK

## Contributing

1. Create a feature branch
2. Make your changes
3. Write/update tests
4. Ensure all tests pass
5. Submit a pull request

## License

This project is private and proprietary.