# Demo Journal Entry Management Scripts

This directory contains scripts for managing demo journal entries that showcase Cassidy's productivity insights capabilities.

## 🎯 Overview

The demo entries are strategically designed to demonstrate:
- **Pattern Recognition** - Peak productivity times, energy drains
- **Mood-Productivity Correlations** - Exercise → clarity, meetings → fatigue  
- **Task Intelligence** - Automatic extraction and tracking
- **Work-Life Balance** - Optimal integration strategies
- **Stress Management** - Identifying triggers and solutions

## 📁 Available Scripts

### 🚀 `manage_demo_entries.py` (RECOMMENDED)
**The main script for managing demo entries in both local and production**

#### Quick Commands:

```bash
# LOCAL TESTING (recommended first step)
cd backend
uv run python scripts/manage_demo_entries.py --reset-demo

# PRODUCTION DEPLOYMENT (after testing locally)
uv run python scripts/manage_demo_entries.py --reset-demo --production

# LIST CURRENT ENTRIES
uv run python scripts/manage_demo_entries.py --list [--production]

# DELETE ONLY (without creating new)
uv run python scripts/manage_demo_entries.py --delete-only [--production]
```

### 📝 Legacy Scripts (for reference)
- `create_test_journal_entries.py` - Basic test entries (7 simple entries)
- `create_demo_journal_entries.py` - Original demo script (local only)

## 🎬 Demo Workflow

### 1. **Test Locally First**
```bash
cd backend

# Check current entries
uv run python scripts/manage_demo_entries.py --list

# Reset with demo entries (WORKAROUND for SQLite transaction issues)
uv run python scripts/manage_demo_entries.py --delete-only
uv run python scripts/create_demo_journal_entries.py

# Verify creation (should show exactly 10 entries)
uv run python scripts/manage_demo_entries.py --list
```

**Note:** There's a known issue with SQLite transaction isolation in the local environment. The workaround above ensures clean deletion before creation.

### 2. **Deploy to Production**
```bash
# Make sure AWS CLI is configured
aws sts get-caller-identity

# Reset production demo entries
uv run python scripts/manage_demo_entries.py --reset-demo --production

# Verify in production
uv run python scripts/manage_demo_entries.py --list --production
```

## 📊 What the Demo Entries Showcase

### Entry Progression (14 days):
1. **Project Kickoff** - Goal setting, team alignment
2. **Deep Work Session** - Peak productivity identification (2-6 PM)
3. **Meeting Overload** - Productivity drain patterns
4. **Wellness Focus** - Exercise-performance correlation
5. **Weekly Review** - Reflection and planning benefits
6. **Social Recharge** - Work-life balance impact
7. **Crisis Management** - Stress response and resilience
8. **Learning & Growth** - Evening study effectiveness
9. **Balanced Day** - Optimal work-life integration
10. **Sprint Success** - Achievement and team performance

### Expected Insights:
- **Peak Times**: Tuesday afternoons, Thursday mornings
- **Energy Killers**: 4+ meetings/day, context switching
- **Productivity Boosters**: Morning workouts, clear boundaries
- **Optimal Schedule**: Exercise → Deep Work → Planning → Social

## 🔧 Technical Details

### Database Connections:
- **Local**: SQLite (`backend/cassidy.db`)
- **Production**: AWS RDS PostgreSQL (auto-detected via CloudFormation)

### Prerequisites for Production:
```bash
# AWS CLI configured
aws configure list

# Access to Cassidy infrastructure
aws cloudformation describe-stacks --stack-name CassidyBackendStack

# Python dependencies
pip install boto3 asyncpg
```

### Environment Detection:
The script automatically detects and connects to the appropriate database:
- Local: Uses SQLite connection string
- Production: Queries AWS CloudFormation and Secrets Manager

## ⚠️ Important Notes

### For Production:
1. **Always test locally first** before deploying to production
2. **Backup existing data** if needed (use existing backup scripts)
3. **Verify AWS access** before running production commands
4. **Production deletes ALL existing entries** for the test user

### For Development:
1. Test user must exist (`user_123` with password `1234`)
2. Database must be initialized
3. All dependencies must be installed

## 🚨 Troubleshooting

### Common Issues:

**1. "Test user not found"**
```bash
# Create test user (local)
cd backend
python -c "from app.core.setup import create_test_user; import asyncio; asyncio.run(create_test_user())"

# Create test user (production)
cd infrastructure
python setup_test_user.py $(cat .backend-url)
```

**2. "Database connection failed"**
```bash
# Local: Check if database file exists
ls -la backend/cassidy.db

# Production: Check AWS access
aws sts get-caller-identity
aws cloudformation describe-stacks --stack-name CassidyBackendStack
```

**3. "AWS credentials not found"**
```bash
aws configure list
aws configure set region us-east-1  # or your region
```

**4. "Module import errors"**
```bash
# Make sure you're in the backend directory
cd backend
python scripts/manage_demo_entries.py --help
```

## 📈 Demo Presentation Tips

### Key Points to Highlight:
1. **Natural Language Input** - Show how free-form text becomes structured data
2. **Pattern Recognition** - Point out recurring productivity patterns
3. **Actionable Insights** - Emphasize specific, practical recommendations
4. **Correlation Detection** - Exercise → productivity, meetings → fatigue

### Demo Flow:
1. **Show Journal Entries** - Natural variety of content
2. **Navigate to Insights** - Patterns and trends identified
3. **Highlight Recommendations** - Specific actions suggested
4. **Emphasize Value** - "Would take months to notice manually"

### Success Metrics:
- Audience understands automatic structuring
- Recognition of valuable patterns
- Appreciation for actionable recommendations
- Interest in implementing similar tracking

---

## 🆘 Need Help?

1. **Check this README** first
2. **Test locally** before production
3. **Verify AWS access** for production issues
4. **Review error messages** - they're usually specific
5. **Check existing backup/setup scripts** in this directory

Happy demoing! 🎉