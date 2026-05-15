# Phase 1 Command-Line Cheatsheet

## Instant Setup (Copy & Paste Ready)

### 1️⃣ Environment & Dependencies (5 minutes)

```bash
# Navigate to project
cd d:\review-sentiment

# Activate virtual environment
.venv\Scripts\activate

# Install new packages (add to existing environment)
pip install flask-jwt-extended python-jose redis flask-caching psycopg2-binary pytest pytest-cov

# Verify installation
pip list | findstr flask-jwt

# Create requirements files for documentation
pip freeze > requirements.txt
pip freeze > requirements-dev.txt
```

### 2️⃣ Project Structure (10 minutes)

```bash
# Create directory structure
mkdir app
mkdir app\auth
mkdir app\core
mkdir app\sentiment
mkdir app\scraping
mkdir app\ml
mkdir app\cache
mkdir app\logging
mkdir app\monitoring
mkdir app\api
mkdir app\utils

mkdir tests
mkdir tests\unit
mkdir tests\integration
mkdir tests\fixtures

mkdir kubernetes
mkdir scripts
mkdir docs
mkdir logs

# Create Python package files (Windows PowerShell)
New-Item -Path app -Name __init__.py -ItemType File
New-Item -Path app\auth -Name __init__.py -ItemType File
New-Item -Path app\core -Name __init__.py -ItemType File
New-Item -Path app\api -Name __init__.py -ItemType File
New-Item -Path tests -Name conftest.py -ItemType File
New-Item -Path tests\unit -Name __init__.py -ItemType File
New-Item -Path tests\integration -Name __init__.py -ItemType File
```

### 3️⃣ Local Database Setup (15 minutes)

```bash
# Using PostgreSQL with Docker
docker pull postgres:13
docker run --name sentiment-db `
  -e POSTGRES_USER=user `
  -e POSTGRES_PASSWORD=password `
  -e POSTGRES_DB=sentiment_db `
  -p 5432:5432 `
  -d postgres:13

# Verify connection
psql -h localhost -U user -d sentiment_db -c "SELECT version();"

# Or use Docker Compose (recommended)
docker-compose up -d
```

### 4️⃣ Redis Setup (5 minutes)

```bash
# Redis with Docker
docker pull redis:6-alpine
docker run --name sentiment-redis `
  -p 6379:6379 `
  -d redis:6-alpine

# Verify connection
redis-cli ping  # Should return "PONG"
```

---

## File Creation Checklist (Parallel Tasks)

### Create Core Configuration Files

**File 1: `config.py`** (100 lines)
```python
import os
from datetime import timedelta

class Config:
    """Base configuration"""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///app.db')
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False

def get_config():
    env = os.getenv('FLASK_ENV', 'development')
    configs = {
        'development': DevelopmentConfig,
        'testing': TestingConfig,
        'production': ProductionConfig
    }
    return configs.get(env, DevelopmentConfig)
```

**File 2: `wsgi.py`** (10 lines)
```python
import os
from app import create_app
from config import get_config

app = create_app(get_config())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=os.getenv('DEBUG', False))
```

**File 3: `.env.example`** (30 lines)
```
FLASK_ENV=development
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here
DATABASE_URL=postgresql://user:password@localhost:5432/sentiment_db
REDIS_URL=redis://localhost:6379/0
LOG_LEVEL=INFO
```

---

## Week 1 Daily Tasks

### Day 1: Structure & Config (2-3 hours)

```bash
# Create and verify files
echo "Creating config.py..." && \
cat > config.py << 'EOF'
[paste config.py content from above]
EOF

echo "Creating wsgi.py..." && \
cat > wsgi.py << 'EOF'
[paste wsgi.py content]
EOF

echo "Creating .env.example..." && \
cat > .env.example << 'EOF'
[paste .env.example content]
EOF

# Copy to .env for local development
copy .env.example .env

# Test configuration loads
python -c "from config import get_config; print('✓ Config loaded:', get_config())"

# Create data directory
mkdir -p instance
mkdir -p logs
```

### Day 2: Database Models (3-4 hours)

```bash
# Create User model file
cat > app\core\models.py << 'EOF'
[User and ReviewRecord models from PRODUCTION_IMPLEMENTATION_PLAN.md]
EOF

# Create database initialization
cat > app\core\database.py << 'EOF'
[Database init code from plan]
EOF

# Test model creation
python -c "from app.core.models import User; print('✓ Models loaded')"
```

### Day 3-4: Application Factory (3-4 hours)

```bash
# Create app factory
cat > app\__init__.py << 'EOF'
[Application factory code]
EOF

# Test app creation
python -c "from app import create_app; app = create_app(); print('✓ App created')"

# Initialize database
python << 'EOF'
from app import create_app
from app.core.database import db

app = create_app()
with app.app_context():
    db.create_all()
    print('✓ Database tables created')
EOF

# Verify database
psql -h localhost -U user -d sentiment_db -c "\dt"
```

---

## Week 2 Daily Tasks (Authentication)

### Day 1-2: User Model & Password Hashing (3 hours)

```bash
# Create authentication models
cat > app\auth\models.py << 'EOF'
[User, APIKey models from plan]
EOF

# Test models
python << 'EOF'
from app.core.database import db
from app.auth.models import User
user = User(username='test', email='test@example.com')
user.set_password('password123')
print(f'✓ Password hashed: {user.password_hash[:20]}...')
print(f'✓ Password check: {user.check_password("password123")}')
EOF
```

### Day 3-4: Authentication Routes (4 hours)

```bash
# Create auth routes
cat > app\auth\routes.py << 'EOF'
[Routes: register, login, refresh, me from plan]
EOF

# Create middleware
cat > app\auth\middleware.py << 'EOF'
[role_required, rate_limit decorators]
EOF

# Test routes (manually or with client)
python << 'EOF'
from app import create_app
from config import TestingConfig

app = create_app(TestingConfig)
client = app.test_client()

# Test registration
resp = client.post('/auth/register', json={
    'username': 'testuser',
    'email': 'test@example.com',
    'password': 'secure123'
})
print(f'Registration: {resp.status_code}')

# Test login
resp = client.post('/auth/login', json={
    'username': 'testuser',
    'password': 'secure123'
})
print(f'Login: {resp.status_code}')
if resp.status_code == 200:
    print(f'✓ Token received: {resp.json["access_token"][:20]}...')
EOF
```

---

## Week 3 Daily Tasks (Database Upgrade)

### Day 1-2: Schema Migration Planning (2 hours)

```bash
# Backup current SQLite database
copy review_sentiment.db review_sentiment.db.backup

# Export to CSV (for validation)
sqlite3 review_sentiment.db << 'EOF'
.headers on
.mode csv
.output review_records_backup.csv
SELECT * FROM reviews;
EOF

# Check record count
sqlite3 review_sentiment.db "SELECT COUNT(*) FROM reviews;"
```

### Day 3-4: PostgreSQL Migration (3 hours)

```bash
# Create migration script
cat > scripts\migrate_sqlite_to_postgresql.py << 'EOF'
import sqlite3
import psycopg2
from psycopg2.extras import execute_values

# Connect to both databases
sqlite_conn = sqlite3.connect('review_sentiment.db')
sqlite_conn.row_factory = sqlite3.Row
sqlite_cursor = sqlite_conn.cursor()

pg_conn = psycopg2.connect(
    dbname='sentiment_db',
    user='user',
    password='password',
    host='localhost'
)
pg_cursor = pg_conn.cursor()

# Create PostgreSQL tables
pg_cursor.execute('''
    CREATE TABLE IF NOT EXISTS review_records (
        id SERIAL PRIMARY KEY,
        text TEXT,
        sentiment VARCHAR(20),
        compound_score FLOAT,
        positive_score FLOAT,
        negative_score FLOAT,
        neutral_score FLOAT,
        confidence FLOAT,
        created_at TIMESTAMP DEFAULT NOW()
    )
''')

# Migrate data
sqlite_cursor.execute('SELECT * FROM reviews')
rows = sqlite_cursor.fetchall()
print(f'Migrating {len(rows)} records...')

for row in rows:
    pg_cursor.execute('''
        INSERT INTO review_records 
        (text, sentiment, compound_score, positive_score, negative_score, neutral_score)
        VALUES (%s, %s, %s, %s, %s, %s)
    ''', tuple(row))

pg_conn.commit()
print('✓ Migration complete!')
EOF

# Run migration
python scripts\migrate_sqlite_to_postgresql.py

# Verify
psql -h localhost -U user -d sentiment_db -c "SELECT COUNT(*) FROM review_records;"
```

---

## Week 4 Testing & Validation

### Run Test Suite

```bash
# Create test file structure
mkdir tests
mkdir tests\unit
mkdir tests\integration

# Create basic test
cat > tests\unit\test_auth.py << 'EOF'
import pytest
from app import create_app
from app.core.database import db
from config import TestingConfig

@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def test_user_registration(client):
    response = client.post('/auth/register', json={
        'username': 'newuser',
        'email': 'new@example.com',
        'password': 'password123'
    })
    assert response.status_code == 201

def test_user_login(client):
    # Register
    client.post('/auth/register', json={
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'password123'
    })
    
    # Login
    response = client.post('/auth/login', json={
        'username': 'testuser',
        'password': 'password123'
    })
    assert response.status_code == 200
    assert 'access_token' in response.json
EOF

# Run tests
pytest tests/unit/test_auth.py -v

# Check coverage
pytest tests/unit/ -v --cov=app --cov-report=html

# Open coverage report
start htmlcov\index.html
```

### Verification Checklist

```bash
# Database ✓
psql -h localhost -U user -d sentiment_db -c "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"

# Redis ✓
redis-cli ping

# Config ✓
python -c "from config import get_config; c = get_config(); print(f'Database: {c.SQLALCHEMY_DATABASE_URI}')"

# App Factory ✓
python -c "from app import create_app; app = create_app(); print('✓ App initialized')"

# Authentication ✓
pytest tests/unit/test_auth.py::test_user_login -v

# Test Coverage ✓
pytest tests/ --cov=app --cov-report=term-missing | grep "TOTAL"
```

---

## Common Commands (Quick Reference)

```bash
# Development Server
python wsgi.py
# or
flask run

# Test Suite
pytest tests/ -v --cov=app

# Database Shell
psql -h localhost -U user -d sentiment_db

# Redis Monitor
redis-cli MONITOR

# View Logs
tail -f logs/app.log

# Docker Logs
docker logs sentiment-db
docker logs sentiment-redis

# Freeze Dependencies
pip freeze > requirements.txt

# Virtual Environment Reset
deactivate
Remove-Item .venv -Recurse
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

---

## Debugging Tips

### Issue: "Cannot connect to PostgreSQL"
```bash
# Check if Docker container is running
docker ps | findstr postgres

# View container logs
docker logs sentiment-db

# Reconnect
psql -h localhost -U user -d sentiment_db -c "SELECT 1"
```

### Issue: "Import Error: No module named 'flask_jwt_extended'"
```bash
# Reinstall packages
pip install --upgrade flask-jwt-extended python-jose
pip show flask-jwt-extended
```

### Issue: "JWT token invalid"
```bash
# Verify token in Python shell
python << 'EOF'
from flask_jwt_extended import create_access_token, decode_token
from config import Config

token = create_access_token(identity=1)
decoded = decode_token(token)
print(f'✓ Token valid: {decoded}')
EOF
```

### Issue: "ConfigAttributeError"
```bash
# Check Flask config
python -c "from app import create_app; app = create_app(); print(app.config)"

# Verify .env file loaded
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('SECRET_KEY'))"
```

---

## Success Markers for Phase 1

✅ **By End of Week 1**
- [ ] Project structure created and files organized
- [ ] `config.py` loads without errors
- [ ] PostgreSQL and Redis running in Docker
- [ ] `.env` and `.env.example` created

✅ **By End of Week 2**
- [ ] User model created with password hashing
- [ ] `/auth/register` endpoint working
- [ ] `/auth/login` endpoint returning JWT tokens
- [ ] JWT tokens validate correctly

✅ **By End of Week 3**
- [ ] SQLite data migrated to PostgreSQL
- [ ] Data integrity verified (row counts match)
- [ ] Database indexes created
- [ ] Query performance improved

✅ **By End of Week 4**
- [ ] 80%+ test coverage for auth module
- [ ] All endpoints secured with @jwt_required
- [ ] Role-based access control working
- [ ] Integration tests passing

---

## Resource Links

- JWT Standard: https://tools.ietf.org/html/rfc7519
- Flask-JWT-Extended: https://flask-jwt-extended.readthedocs.io/
- PostgreSQL Docker: https://hub.docker.com/_/postgres
- Redis Docker: https://hub.docker.com/r/library/redis
- Pytest Fixtures: https://docs.pytest.org/en/stable/fixture.html

---

**Total Phase 1 Time: 32 hours spread over 4 weeks**  
**Recommended: 2 hours per day, 4 days per week**

