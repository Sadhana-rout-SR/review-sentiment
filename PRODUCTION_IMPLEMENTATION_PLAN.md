# Sentiment Review Analyzer - Production Implementation Plan
## From 7.5/10 to Enterprise-Grade System

**Last Updated:** March 11, 2026  
**Target Completion:** 24 weeks / 220 hours / Production-Ready  
**Team Level:** Senior Architecture + Mid-level Development (2-3 FTE)

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Pre-Implementation Checklist](#pre-implementation-checklist)
3. [Phase 1: Foundation & Security (Weeks 1-4)](#phase-1-foundation--security-weeks-1-4)
4. [Phase 2: Performance & Optimization (Weeks 5-8)](#phase-2-performance--optimization-weeks-5-8)
5. [Phase 3: Advanced NLP & ML (Weeks 9-14)](#phase-3-advanced-nlp--ml-weeks-9-14)
6. [Phase 4: Async Processing & Scalability (Weeks 15-19)](#phase-4-async-processing--scalability-weeks-15-19)
7. [Phase 5: Monitoring, Testing & Deployment (Weeks 20-24)](#phase-5-monitoring-testing--deployment-weeks-20-24)
8. [Code Architecture Changes](#code-architecture-changes)
9. [Database Schema Evolution](#database-schema-evolution)
10. [Deployment Architecture](#deployment-architecture)
11. [Success Metrics & KPIs](#success-metrics--kpis)

---

## Executive Summary

### Current State Assessment
- **Overall Score:** 7.5/10
- **Strengths:** Multi-source scraping, responsive UI, modular code structure
- **Gaps:** No authentication, basic sentiment model (VADER only), synchronous processing, no caching
- **Risk Level:** MVP quality, not production-ready for enterprise use

### Target State
- **Overall Score:** 9.2/10
- **Production-Ready Features:**
  - Enterprise authentication with JWT + role-based access control
  - Ensemble NLP (BERT + DistilBERT + VADER) for 85%+ accuracy
  - ML-based fake review detection (82% precision)
  - Sub-200ms report load times with Redis caching
  - Async scraping and analysis with Celery
  - Comprehensive logging with ELK stack integration
  - Kubernetes-ready containerization
  - 99.9% uptime capability

### Investment Breakdown

| Phase | Focus | Hours | Cost | Duration |
|-------|-------|-------|------|----------|
| 1 | Auth, Security, Setup | 32 | $6,400 | 1 month |
| 2 | Caching, Optimization | 24 | $4,800 | 1 month |
| 3 | BERT, ML Models | 64 | $12,800 | 1.5 months |
| 4 | Celery, Async | 56 | $11,200 | 1.25 months |
| 5 | Logging, Testing, Deploy | 44 | $8,800 | 1.25 months |
| **TOTAL** | **Production Ready** | **220** | **$44,000** | **6 months** |

### Success Criteria (By End of Phase 5)
- ✅ Zero unauthenticated endpoints
- ✅ Sentiment accuracy 85%+ (measured on test set)
- ✅ Fake detection precision 82% (measured on labeled dataset)
- ✅ P95 report load time <200ms
- ✅ 95% test coverage (unit + integration)
- ✅ Kubernetes deployment with auto-scaling
- ✅ <30-minute MTTR on production incidents
- ✅ Monthly release cycle capability

---

## Pre-Implementation Checklist

### Prerequisites to Complete BEFORE Phase 1 Starts

- [ ] **Environment Setup**
  - [ ] Python 3.10+ confirmed
  - [ ] PostgreSQL 13+ installed (upgrade from SQLite for production)
  - [ ] Redis 6.0+ installed locally
  - [ ] Docker 20.10+ installed
  - [ ] Kubernetes cluster access (Minikube for dev, cloud for prod)

- [ ] **Dependency Audit**
  - [ ] Review all current requirements.txt packages for security vulnerabilities
  - [ ] Plan new dependencies: `flask-jwt-extended`, `redis`, `celery`, `torch`, `transformers`, `scikit-learn`, `prometheus-client`, `python-json-logger`
  - [ ] Estimated 15-20 new packages (increase image size from ~200MB to ~1.2GB)

- [ ] **Data & Infrastructure**
  - [ ] Backup current SQLite database (export to CSV)
  - [ ] Plan PostgreSQL migration strategy
  - [ ] Prepare Redis memory allocation (minimum 2GB for production)
  - [ ] Setup Docker registry (Docker Hub or private)

- [ ] **Team & Process**
  - [ ] Assign code review pairs for each phase
  - [ ] Setup CI/CD pipeline skeleton (GitHub Actions or Jenkins)
  - [ ] Establish sprint schedule (2-week sprints recommended)
  - [ ] Create architecture decision record (ADR) document

- [ ] **Testing Data**
  - [ ] Collect 1000+ reviews for sentiment model validation
  - [ ] Manually label 500 reviews for fake detection training
  - [ ] Create performance baseline measurements
  - [ ] Setup staging environment mirroring production

---

## PHASE 1: Foundation & Security (Weeks 1-4)

### 1.1 Project Structure Refactoring

**Objective:** Modularize codebase for scalability and testability  
**Effort:** 8 hours | **Priority:** CRITICAL

#### Current Structure:
```
review-sentiment/
├── app.py (monolithic, everything here)
├── scraper.py
├── sentiment.py
├── database.py
├── requirements.txt
├── templates/
│   └── index.html
└── static/
    └── style.css
```

#### Target Structure:
```
review-sentiment/
├── config.py                          # Environment config
├── wsgi.py                            # Production entry point
├── requirements.txt                   # Base dependencies
├── requirements-dev.txt               # Dev dependencies
├── requirements-ml.txt                # ML dependencies
├── pytest.ini                         # Test configuration
├── Dockerfile                         # Container config
├── docker-compose.yml                 # Local dev stack
├── kubernetes/                        # K8s manifests
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── configmap.yaml
│   └── ingress.yaml
├── app/                               # Main application package
│   ├── __init__.py
│   ├── auth/                          # NEW: Authentication
│   │   ├── __init__.py
│   │   ├── models.py                  # User, Role models
│   │   ├── routes.py                  # Login, register, JWT
│   │   ├── middleware.py              # Auth decorators
│   │   └── utils.py                   # Token validation
│   ├── core/
│   │   ├── __init__.py
│   │   ├── models.py                  # Database models
│   │   ├── database.py                # DB initialization
│   │   └── exceptions.py              # Custom exceptions
│   ├── sentiment/                     # Refactored sentiment
│   │   ├── __init__.py
│   │   ├── vader_analyzer.py          # Legacy VADER
│   │   ├── bert_analyzer.py           # NEW: BERT model
│   │   ├── ensemble.py                # NEW: Combined models
│   │   ├── cache_manager.py           # NEW: Model caching
│   │   └── models.py                  # NEW: Hugging Face models
│   ├── scraping/
│   │   ├── __init__.py
│   │   ├── scraper.py                 # Refactored scraper
│   │   ├── validators.py              # Data validation
│   │   └── tasks.py                   # NEW: Celery tasks
│   ├── ml/                            # NEW: Machine Learning
│   │   ├── __init__.py
│   │   ├── fake_detector.py           # Fake review detection
│   │   ├── feature_extractor.py       # Feature engineering
│   │   ├── model_trainer.py           # Training pipeline
│   │   └── preprocessing.py           # Data preprocessing
│   ├── cache/                         # NEW: Caching layer
│   │   ├── __init__.py
│   │   ├── redis_client.py            # Redis interface
│   │   ├── decorators.py              # Cache decorators
│   │   └── strategies.py              # Cache strategies
│   ├── logging/                       # NEW: Logging system
│   │   ├── __init__.py
│   │   ├── logger.py                  # Logger setup
│   │   ├── formatters.py              # JSON formatting
│   │   └── handlers.py                # Log handlers
│   ├── monitoring/                    # NEW: Monitoring
│   │   ├── __init__.py
│   │   ├── metrics.py                 # Prometheus metrics
│   │   ├── health_checks.py           # Health endpoints
│   │   └── alerts.py                  # Alert configuration
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py                  # API endpoints (refactored)
│   │   ├── schemas.py                 # Request/response schemas
│   │   └── decorators.py              # API decorators
│   └── utils/
│       ├── __init__.py
│       ├── helpers.py
│       └── validators.py
├── tests/                             # NEW: Test suite
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_sentiment.py
│   │   ├── test_auth.py
│   │   └── test_ml.py
│   ├── integration/
│   │   ├── test_api.py
│   │   └── test_database.py
│   └── fixtures/
│       ├── sample_reviews.json
│       └── test_data.sql
└── scripts/                           # NEW: Utility scripts
    ├── init_db.py                     # Database initialization
    ├── migrate_data.py                # SQLite → PostgreSQL
    ├── train_models.py                # ML training script
    └── generate_metrics.py            # Performance benchmarks
```

**Implementation Steps:**

```python
# 1. Create config.py with environment-based configuration
# config.py
import os
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()

class Config:
    """Base configuration"""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # Redis
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    CACHE_DEFAULT_TIMEOUT = 300
    
    # Celery
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/1')
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/2')
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'sqlite:///review_sentiment.db'
    )
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FORMAT = 'json'  # 'json' or 'text'

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    SQLALCHEMY_ECHO = True

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=5)

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    SQLALCHEMY_ECHO = False

def get_config():
    """Return appropriate config based on environment"""
    env = os.getenv('FLASK_ENV', 'development')
    config_map = {
        'development': DevelopmentConfig,
        'testing': TestingConfig,
        'production': ProductionConfig,
    }
    return config_map.get(env, DevelopmentConfig)
```

```python
# 2. Create application factory (app/__init__.py)
# app/__init__.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from app.core.database import db, init_db
from app.cache.redis_client import cache
from config import get_config

jwt = JWTManager()

def create_app(config=None):
    """Application factory"""
    app = Flask(__name__)
    
    # Load configuration
    if config is None:
        config = get_config()
    app.config.from_object(config)
    
    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    cache.init_app(app)
    
    # Register blueprints
    from app.auth.routes import auth_bp
    from app.api.routes import api_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Initialize database
    with app.app_context():
        init_db()
    
    return app
```

### 1.2 User Authentication & Authorization

**Objective:** Implement JWT-based authentication with role-based access control  
**Effort:** 12 hours | **Priority:** CRITICAL

#### New File: `app/auth/models.py`

```python
from datetime import datetime
from app.core.database import db
from werkzeug.security import generate_password_hash, check_password_hash
from enum import Enum

class UserRole(Enum):
    """User roles for authorization"""
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"

class User(db.Model):
    """User model for authentication"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(
        db.String(20),
        default=UserRole.VIEWER.value,
        nullable=False
    )
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    api_keys = db.relationship('APIKey', backref='user', lazy='dynamic')
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify password"""
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat()
        }

class APIKey(db.Model):
    """API key model for programmatic access"""
    __tablename__ = 'api_keys'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    key = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used = db.Column(db.DateTime)
    
    def generate_key(self):
        """Generate a new API key"""
        import secrets
        self.key = secrets.token_urlsafe(32)
        return self.key
```

#### New File: `app/auth/routes.py`

```python
from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity
)
from app.core.database import db
from app.auth.models import User, UserRole
from datetime import datetime

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    data = request.get_json()
    
    # Validation
    if not data.get('username') or not data.get('password') or not data.get('email'):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Check if user exists
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 409
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists'}), 409
    
    # Create user
    user = User(
        username=data['username'],
        email=data['email'],
        role=UserRole.VIEWER.value  # Default role
    )
    user.set_password(data['password'])
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'message': 'User created successfully',
        'user': user.to_dict()
    }), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate user and return JWT tokens"""
    data = request.get_json()
    
    if not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Missing credentials'}), 400
    
    user = User.query.filter_by(username=data['username']).first()
    
    if not user or not user.check_password(data['password']):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    if not user.is_active:
        return jsonify({'error': 'User account is inactive'}), 403
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    # Create tokens
    access_token = create_access_token(
        identity=user.id,
        additional_claims={'role': user.role}
    )
    refresh_token = create_refresh_token(identity=user.id)
    
    return jsonify({
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': user.to_dict()
    }), 200

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh_access_token():
    """Refresh access token using refresh token"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user or not user.is_active:
        return jsonify({'error': 'Invalid user'}), 401
    
    access_token = create_access_token(
        identity=user.id,
        additional_claims={'role': user.role}
    )
    
    return jsonify({'access_token': access_token}), 200

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Get current authenticated user"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify(user.to_dict()), 200
```

#### New File: `app/auth/middleware.py`

```python
from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt

def role_required(required_role):
    """Decorator to enforce role-based access control"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            user_role = claims.get('role')
            
            # Role hierarchy: admin > analyst > viewer
            role_hierarchy = {'admin': 3, 'analyst': 2, 'viewer': 1}
            
            if role_hierarchy.get(user_role, 0) < role_hierarchy.get(required_role, 0):
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def rate_limit(limit=100, per_time=300):  # 100 requests per 5 minutes
    """Decorator for rate limiting"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # Using Redis for rate limiting (implementation in Phase 2)
            return fn(*args, **kwargs)
        return wrapper
    return decorator
```

### 1.3 Update Database Schema

**Objective:** Prepare database for new features  
**Effort:** 4 hours | **Priority:** HIGH

#### Enhanced `app/core/models.py`

```python
from datetime import datetime
from app.core.database import db

class AnalysisRun(db.Model):
    """Analysis session metadata"""
    __tablename__ = 'analysis_runs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    query = db.Column(db.String(500), nullable=False)
    source = db.Column(db.String(50), nullable=False)  # google, maps, website
    status = db.Column(db.String(20), default='completed')  # pending, running, completed, failed
    total_reviews = db.Column(db.Integer, default=0)
    filtered_reviews = db.Column(db.Integer, default=0)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    # Relationships
    user = db.relationship('User', backref='analysis_runs')
    reviews = db.relationship('ReviewRecord', backref='analysis_run', lazy='dynamic')

class ReviewRecord(db.Model):
    """Individual review data"""
    __tablename__ = 'review_records'
    
    id = db.Column(db.Integer, primary_key=True)
    analysis_run_id = db.Column(
        db.Integer,
        db.ForeignKey('analysis_runs.id'),
        nullable=False
    )
    
    # Review content
    text = db.Column(db.Text, nullable=False)
    reviewer_name = db.Column(db.String(255))
    reviewer_id = db.Column(db.String(255))
    
    # VADER sentiment (Phase 1)
    sentiment = db.Column(db.String(20))  # Positive, Negative, Neutral
    compound_score = db.Column(db.Float)
    positive_score = db.Column(db.Float)
    negative_score = db.Column(db.Float)
    neutral_score = db.Column(db.Float)
    confidence = db.Column(db.Float)
    
    # BERT sentiment (Phase 3)
    bert_sentiment = db.Column(db.String(20))
    bert_score = db.Column(db.Float)
    bert_confidence = db.Column(db.Float)
    
    # Ensemble result (Phase 3)
    ensemble_sentiment = db.Column(db.String(20))
    ensemble_score = db.Column(db.Float)
    ensemble_confidence = db.Column(db.Float)
    
    # Fake review detection (Phase 3)
    is_fake = db.Column(db.Boolean, default=False)
    fake_probability = db.Column(db.Float)
    fake_reason = db.Column(db.String(255))
    
    # Metadata
    rating = db.Column(db.Float)
    review_date = db.Column(db.DateTime)
    source = db.Column(db.String(50))  # google, maps, website, etc.
    source_url = db.Column(db.String(500))
    
    # Processing metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime)
    
    def to_dict(self):
        return {
            'id': self.id,
            'text': self.text,
            'reviewer_name': self.reviewer_name,
            'sentiment': self.sentiment,
            'bert_sentiment': self.bert_sentiment,
            'ensemble_sentiment': self.ensemble_sentiment,
            'is_fake': self.is_fake,
            'fake_probability': self.fake_probability,
            'rating': self.rating,
            'review_date': self.review_date.isoformat() if self.review_date else None,
            'source': self.source,
        }

class DailyAnalytics(db.Model):
    """Aggregated daily statistics"""
    __tablename__ = 'daily_analytics'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    
    # Review counts
    total_reviews = db.Column(db.Integer, default=0)
    positive_count = db.Column(db.Integer, default=0)
    negative_count = db.Column(db.Integer, default=0)
    neutral_count = db.Column(db.Integer, default=0)
    fake_count = db.Column(db.Integer, default=0)
    
    # Sentiment averages (VADER)
    avg_compound_score = db.Column(db.Float)
    avg_positive_score = db.Column(db.Float)
    avg_negative_score = db.Column(db.Float)
    
    # Sentiment averages (BERT)
    bert_avg_score = db.Column(db.Float)
    
    # Ensemble averages
    ensemble_avg_score = db.Column(db.Float)
    
    # Fake detection stats
    fake_detection_rate = db.Column(db.Float)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

### 1.4 Environment Configuration

**Objective:** Setup production-ready environment configuration  
**Effort:** 2 hours | **Priority:** HIGH

Create `.env.example`:
```
# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=False
SECRET_KEY=your-secret-key-here
LOG_LEVEL=INFO

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/sentiment_db
# For development: sqlite:///review_sentiment.db

# JWT Configuration
JWT_SECRET_KEY=your-jwt-secret-key-here
JWT_ACCESS_TOKEN_EXPIRES=3600
JWT_REFRESH_TOKEN_EXPIRES=2592000

# Redis Configuration
REDIS_URL=redis://localhost:6379/0
CACHE_DEFAULT_TIMEOUT=300

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Sentiment Analysis
VADER_THRESHOLD_POSITIVE=0.05
VADER_THRESHOLD_NEGATIVE=-0.05
USE_BERT_MODEL=False  # True in Phase 3

# Scraping Configuration
SCRAPER_TIMEOUT=45
SCRAPER_MAX_RETRIES=3
GOOGLE_API_KEY=your-google-api-key
BROWSER_HEADLESS=True

# Monitoring
PROMETHEUS_ENABLED=True
HEALTH_CHECK_INTERVAL=60

# Email Configuration (Phase 4)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

### 1.5 Phase 1 Testing & Validation

**Objective:** Ensure auth and structure changes work correctly  
**Effort:** 6 hours | **Priority:** HIGH

Create `tests/unit/test_auth.py`:

```python
import pytest
from app import create_app
from app.core.database import db
from app.auth.models import User, UserRole
from config import TestingConfig

@pytest.fixture
def app():
    """Create application for testing"""
    app = create_app(TestingConfig)
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    """Flask test client"""
    return app.test_client()

def test_user_registration_success(client):
    """Test successful user registration"""
    response = client.post('/auth/register', json={
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'secure_password_123'
    })
    
    assert response.status_code == 201
    data = response.get_json()
    assert data['user']['username'] == 'testuser'
    assert data['user']['role'] == UserRole.VIEWER.value

def test_user_registration_duplicate_username(client):
    """Test registration fails with duplicate username"""
    # Create first user
    client.post('/auth/register', json={
        'username': 'testuser',
        'email': 'test1@example.com',
        'password': 'password123'
    })
    
    # Try to create with same username
    response = client.post('/auth/register', json={
        'username': 'testuser',
        'email': 'test2@example.com',
        'password': 'password123'
    })
    
    assert response.status_code == 409
    assert 'already exists' in response.get_json()['error']

def test_user_login_success(client):
    """Test successful login"""
    # Register user
    client.post('/auth/register', json={
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'secure_password_123'
    })
    
    # Login
    response = client.post('/auth/login', json={
        'username': 'testuser',
        'password': 'secure_password_123'
    })
    
    assert response.status_code == 200
    data = response.get_json()
    assert 'access_token' in data
    assert 'refresh_token' in data

def test_user_login_invalid_password(client):
    """Test login fails with invalid password"""
    client.post('/auth/register', json={
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'secure_password_123'
    })
    
    response = client.post('/auth/login', json={
        'username': 'testuser',
        'password': 'wrong_password'
    })
    
    assert response.status_code == 401

def test_protected_endpoint_requires_auth(client):
    """Test protected endpoints require authentication"""
    response = client.get('/api/me')
    assert response.status_code == 401

def test_protected_endpoint_with_valid_token(client):
    """Test protected endpoint works with valid token"""
    # Register and login
    client.post('/auth/register', json={
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'secure_password_123'
    })
    
    login_resp = client.post('/auth/login', json={
        'username': 'testuser',
        'password': 'secure_password_123'
    })
    
    token = login_resp.get_json()['access_token']
    
    # Access protected endpoint
    response = client.get(
        '/api/me',
        headers={'Authorization': f'Bearer {token}'}
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['username'] == 'testuser'
```

Run tests:
```bash
pytest tests/unit/test_auth.py -v --cov=app/auth
```

### ✅ Phase 1 Deliverables

By end of Week 4, you should have:

1. **Modular project structure** with separation of concerns
2. **JWT authentication system** with login/register/refresh endpoints
3. **Role-based access control** (admin, analyst, viewer)
4. **Environment-based configuration** (dev, test, prod)
5. **Enhanced database models** ready for new features
6. **Unit tests** for authentication (>80% coverage)
7. **Documentation** of new authentication API

**Phase 1 Success Criteria:**
- All unit tests pass
- JWT tokens valid for 1 hour (refresh for 30 days)
- Zero unauthenticated endpoint access without explicit exemption
- Role hierarchy enforced (admin > analyst > viewer)
- Database migrations completed without data loss

---

## PHASE 2: Performance & Optimization (Weeks 5-8)

### 2.1 Redis Caching Implementation

**Objective:** Reduce report loading time from 3-5 seconds to <200ms  
**Effort:** 12 hours | **Priority:** CRITICAL

#### New File: `app/cache/redis_client.py`

```python
import redis
from flask_caching import Cache
from config import Config
from functools import wraps
import json

class RedisClient:
    """Redis client for caching and session management"""
    
    def __init__(self, app=None):
        self.redis = None
        self.cache = Cache()
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app"""
        self.redis = redis.from_url(
            app.config.get('REDIS_URL'),
            decode_responses=True
        )
        self.cache.init_app(
            app,
            config={'CACHE_TYPE': 'redis', 'CACHE_REDIS_URL': app.config['REDIS_URL']}
        )
    
    def get(self, key):
        """Get value from cache"""
        value = self.redis.get(key)
        if value:
            try:
                return json.loads(value)
            except:
                return value
        return None
    
    def set(self, key, value, ttl=300):
        """Set value in cache with TTL"""
        if isinstance(value, dict) or isinstance(value, list):
            value = json.dumps(value)
        self.redis.setex(key, ttl, value)
    
    def delete(self, key):
        """Delete cache entry"""
        self.redis.delete(key)
    
    def clear_pattern(self, pattern):
        """Delete all keys matching pattern"""
        keys = self.redis.keys(pattern)
        if keys:
            self.redis.delete(*keys)
    
    def get_stats(self):
        """Get Redis memory and performance stats"""
        info = self.redis.info()
        return {
            'used_memory': info['used_memory_human'],
            'used_memory_peak': info['used_memory_peak_human'],
            'connected_clients': info['connected_clients'],
            'total_commands_processed': info['total_commands_processed'],
            'keyspace_hits': info['keyspace_hits'],
            'keyspace_misses': info['keyspace_misses'],
        }

cache = RedisClient()
```

#### New File: `app/cache/decorators.py`

```python
from functools import wraps
from app.cache.redis_client import cache
import hashlib
import json

def cached_result(ttl=300, key_prefix=''):
    """Decorator to cache function results"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            cache_key_data = f"{fn.__name__}:{json.dumps(args)}:{json.dumps(kwargs)}"
            cache_key = f"{key_prefix}:{hashlib.md5(cache_key_data.encode()).hexdigest()}"
            
            # Try to get from cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Call function and cache result
            result = fn(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator

def invalidate_cache(pattern):
    """Decorator to invalidate cache after function execution"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            result = fn(*args, **kwargs)
            # Clear cache matching pattern
            cache.clear_pattern(pattern)
            return result
        return wrapper
    return decorator

def cache_if_authenticated(ttl=600):
    """Cache results for authenticated users"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            from flask_jwt_extended import get_jwt_identity
            
            try:
                user_id = get_jwt_identity()
                cache_key = f"user:{user_id}:{fn.__name__}"
                
                cached = cache.get(cache_key)
                if cached:
                    return cached
                
                result = fn(*args, **kwargs)
                cache.set(cache_key, result, ttl)
                return result
            except:
                # Not authenticated, don't cache
                return fn(*args, **kwargs)
        return wrapper
    return decorator
```

#### Update `app/api/routes.py` with Caching

```python
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.auth.middleware import role_required
from app.cache.decorators import cached_result, invalidate_cache, cache_if_authenticated
from app.core.models import ReviewRecord, DailyAnalytics, AnalysisRun
from app.core.database import db
from datetime import datetime, timedelta
from sqlalchemy import func

api_bp = Blueprint('api', __name__)

@api_bp.route('/analytics/daily', methods=['GET'])
@jwt_required()
@cache_if_authenticated(ttl=600)  # Cache for 10 minutes per user
def get_daily_analytics():
    """
    Get 14-day sentiment analytics
    OPTIMIZED: Redis caching reduces query time from 3-5s to <200ms on cache hit
    """
    days = request.args.get('days', 14, type=int)
    
    # Query daily analytics table (pre-aggregated)
    start_date = datetime.utcnow().date() - timedelta(days=days)
    analytics = DailyAnalytics.query.filter(
        DailyAnalytics.date >= start_date
    ).order_by(DailyAnalytics.date.asc()).all()
    
    data = {
        'dates': [a.date.isoformat() for a in analytics],
        'data': {
            'total_reviews': [a.total_reviews for a in analytics],
            'positive_count': [a.positive_count for a in analytics],
            'negative_count': [a.negative_count for a in analytics],
            'neutral_count': [a.neutral_count for a in analytics],
            'fake_count': [a.fake_count for a in analytics],
            'avg_sentiment': [a.ensemble_avg_score or a.avg_compound_score for a in analytics],
        },
        'summary': {
            'total': sum(a.total_reviews for a in analytics),
            'positive': sum(a.positive_count for a in analytics),
            'negative': sum(a.negative_count for a in analytics),
            'neutral': sum(a.neutral_count for a in analytics),
            'fake': sum(a.fake_count for a in analytics),
        }
    }
    
    return jsonify(data), 200

@api_bp.route('/reviews', methods=['GET'])
@jwt_required()
@cache_if_authenticated(ttl=300)  # Cache for 5 minutes
def get_reviews():
    """Get paginated reviews with optional filtering"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    sentiment = request.args.get('sentiment', '')
    source = request.args.get('source', '')
    is_fake = request.args.get('is_fake', '', type=bool)
    
    query = ReviewRecord.query
    
    if sentiment:
        query = query.filter_by(ensemble_sentiment=sentiment)
    if source:
        query = query.filter_by(source=source)
    if is_fake != '':
        query = query.filter_by(is_fake=is_fake)
    
    paginated = query.order_by(
        ReviewRecord.created_at.desc()
    ).paginate(page=page, per_page=per_page)
    
    return jsonify({
        'reviews': [r.to_dict() for r in paginated.items],
        'total': paginated.total,
        'pages': paginated.pages,
        'current_page': page,
    }), 200

@api_bp.route('/analysis/<int:analysis_id>', methods=['GET'])
@jwt_required()
@cached_result(ttl=3600, key_prefix='analysis')  # Cache for 1 hour
def get_analysis(analysis_id):
    """Get analysis results (highly cacheable)"""
    analysis = AnalysisRun.query.get_or_404(analysis_id)
    
    # Summary statistics
    reviews = analysis.reviews.all()
    total = len(reviews)
    
    sentiment_counts = {
        'positive': sum(1 for r in reviews if r.ensemble_sentiment == 'Positive'),
        'negative': sum(1 for r in reviews if r.ensemble_sentiment == 'Negative'),
        'neutral': sum(1 for r in reviews if r.ensemble_sentiment == 'Neutral'),
    }
    
    fake_count = sum(1 for r in reviews if r.is_fake)
    
    return jsonify({
        'id': analysis.id,
        'query': analysis.query,
        'source': analysis.source,
        'status': analysis.status,
        'total_reviews': analysis.total_reviews,
        'filtered_reviews': analysis.filtered_reviews,
        'sentiment_distribution': sentiment_counts,
        'fake_count': fake_count,
        'started_at': analysis.started_at.isoformat(),
        'completed_at': analysis.completed_at.isoformat() if analysis.completed_at else None,
    }), 200

@api_bp.route('/analyze', methods=['POST'])
@jwt_required()
@invalidate_cache(pattern='analysis:*')  # Clear analysis cache after new analysis
def analyze_reviews():
    """Analyze reviews (invalidates cache)"""
    # ... existing analyze logic ...
    # Cache is automatically invalidated after analysis completes
    pass
```

### 2.2 Database Query Optimization

**Objective:** Optimize slow queries with indexing and aggregation  
**Effort:** 6 hours | **Priority:** HIGH

Create `app/core/database.py` with optimizations:

```python
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def init_db():
    """Initialize database with optimizations"""
    # Create all tables
    db.create_all()
    
    # Create indexes for frequently queried columns
    _create_indexes()

def _create_indexes():
    """Create database indexes for performance"""
    # Note: Executed at application startup
    from sqlalchemy import text
    
    indexes = [
        # ReviewRecord indexes
        ("CREATE INDEX IF NOT EXISTS idx_review_analysis_id ON review_records(analysis_run_id)", "Review analysis FK"),
        ("CREATE INDEX IF NOT EXISTS idx_review_sentiment ON review_records(ensemble_sentiment)", "Sentiment filtering"),
        ("CREATE INDEX IF NOT EXISTS idx_review_is_fake ON review_records(is_fake)", "Fake detection"),
        ("CREATE INDEX IF NOT EXISTS idx_review_created_at ON review_records(created_at)", "Date filtering"),
        ("CREATE INDEX IF NOT EXISTS idx_review_source ON review_records(source)", "Source filtering"),
        
        # AnalysisRun indexes
        ("CREATE INDEX IF NOT EXISTS idx_analysis_user_id ON analysis_runs(user_id)", "User analysis FK"),
        ("CREATE INDEX IF NOT EXISTS idx_analysis_status ON analysis_runs(status)", "Status filtering"),
        ("CREATE INDEX IF NOT EXISTS idx_analysis_created_at ON analysis_runs(started_at)", "Date range"),
        
        # DailyAnalytics indexes
        ("CREATE INDEX IF NOT EXISTS idx_daily_analytics_date ON daily_analytics(date)", "Daily lookup"),
        
        # User indexes
        ("CREATE INDEX IF NOT EXISTS idx_user_username ON users(username)", "Auth lookup"),
        ("CREATE INDEX IF NOT EXISTS idx_user_email ON users(email)", "Email lookup"),
    ]
    
    try:
        for sql, description in indexes:
            db.session.execute(text(sql))
        db.session.commit()
        print("✓ Database indexes created successfully")
    except Exception as e:
        print(f"⚠ Index creation warning: {e}")
```

### 2.3 Pre-aggregation Strategy

**Objective:** Pre-compute daily statistics to avoid slow aggregations  
**Effort:** 4 hours | **Priority:** HIGH

Create `app/core/aggregations.py`:

```python
from app.core.database import db
from app.core.models import ReviewRecord, DailyAnalytics, AnalysisRun
from datetime import datetime, timedelta
from sqlalchemy import func

def update_daily_analytics(date=None):
    """
    Update DailyAnalytics for a specific date
    Called after each analysis completion
    """
    if date is None:
        date = datetime.utcnow().date()
    
    # Get all reviews from that day
    start = datetime.combine(date, datetime.min.time())
    end = datetime.combine(date, datetime.max.time())
    
    reviews = ReviewRecord.query.filter(
        ReviewRecord.created_at.between(start, end)
    ).all()
    
    if not reviews:
        return
    
    # Calculate statistics
    total = len(reviews)
    sentiment_counts = {
        'positive': 0,
        'negative': 0,
        'neutral': 0,
    }
    fake_count = 0
    
    sum_compound = 0
    sum_positive = 0
    sum_negative = 0
    sum_bert = 0
    sum_ensemble = 0
    
    for review in reviews:
        # Count by sentiment
        if review.ensemble_sentiment == 'Positive':
            sentiment_counts['positive'] += 1
        elif review.ensemble_sentiment == 'Negative':
            sentiment_counts['negative'] += 1
        else:
            sentiment_counts['neutral'] += 1
        
        # Count fakes
        if review.is_fake:
            fake_count += 1
        
        # Sum scores
        sum_compound += review.compound_score or 0
        sum_positive += review.positive_score or 0
        sum_negative += review.negative_score or 0
        sum_bert += review.bert_score or 0
        sum_ensemble += review.ensemble_score or 0
    
    # Create or update daily analytics
    analytics = DailyAnalytics.query.filter_by(date=date).first()
    if not analytics:
        analytics = DailyAnalytics(date=date)
        db.session.add(analytics)
    
    # Update with calculated values
    analytics.total_reviews = total
    analytics.positive_count = sentiment_counts['positive']
    analytics.negative_count = sentiment_counts['negative']
    analytics.neutral_count = sentiment_counts['neutral']
    analytics.fake_count = fake_count
    
    analytics.avg_compound_score = sum_compound / total if total > 0 else 0
    analytics.avg_positive_score = sum_positive / total if total > 0 else 0
    analytics.avg_negative_score = sum_negative / total if total > 0 else 0
    analytics.bert_avg_score = sum_bert / total if total > 0 else 0
    analytics.ensemble_avg_score = sum_ensemble / total if total > 0 else 0
    analytics.fake_detection_rate = (fake_count / total * 100) if total > 0 else 0
    
    db.session.commit()

def regenerate_all_analytics():
    """
    Regenerate all daily analytics
    Run when migrating data or recovering from inconsistency
    """
    # Get all unique dates from reviews
    dates = db.session.query(
        func.date(ReviewRecord.created_at)
    ).distinct().all()
    
    for date_tuple in dates:
        date = date_tuple[0]
        update_daily_analytics(date)
        print(f"✓ Analytics updated for {date}")

def get_analytics_range(start_date, end_date):
    """
    Get analytics for date range
    Used by dashboard
    """
    analytics = DailyAnalytics.query.filter(
        DailyAnalytics.date.between(start_date, end_date)
    ).order_by(DailyAnalytics.date.asc()).all()
    
    return [
        {
            'date': a.date.isoformat(),
            'total_reviews': a.total_reviews,
            'positive': a.positive_count,
            'negative': a.negative_count,
            'neutral': a.neutral_count,
            'fake': a.fake_count,
            'avg_score': a.ensemble_avg_score or a.avg_compound_score,
        }
        for a in analytics
    ]
```

### 2.4 Response Time Benchmarking

**Objective:** Measure and validate performance improvements  
**Effort:** 2 hours | **Priority:** MEDIUM

Create `tests/performance/benchmark_queries.py`:

```python
import time
import statistics
from app import create_app
from app.core.database import db
from config import DevelopmentConfig

def benchmark_query(query_fn, iterations=10):
    """Benchmark a query function"""
    times = []
    
    for _ in range(iterations):
        start = time.perf_counter()
        result = query_fn()
        end = time.perf_counter()
        times.append((end - start) * 1000)  # Convert to ms
    
    return {
        'min': min(times),
        'max': max(times),
        'mean': statistics.mean(times),
        'median': statistics.median(times),
        'stdev': statistics.stdev(times) if len(times) > 1 else 0,
        'total_calls': iterations,
    }

def main():
    app = create_app(DevelopmentConfig)
    
    with app.app_context():
        print("=" * 60)
        print("Query Performance Benchmark")
        print("=" * 60)
        
        # Test 1: Daily analytics query without cache
        print("\n[1] Daily Analytics (14 days) - WITHOUT CACHE")
        from app.core.models import ReviewRecord
        from datetime import datetime, timedelta
        
        def query_daily():
            start_date = datetime.utcnow().date() - timedelta(days=14)
            return db.session.query(ReviewRecord).filter(
                ReviewRecord.created_at >= start_date
            ).all()
        
        results = benchmark_query(query_daily, 5)
        print(f"  Mean: {results['mean']:.2f}ms")
        print(f"  Min:  {results['min']:.2f}ms")
        print(f"  Max:  {results['max']:.2f}ms")
        
        # Test 2: With pre-aggregated table
        print("\n[2] Daily Analytics (14 days) - PRE-AGGREGATED (with cache)")
        from app.core.models import DailyAnalytics
        
        def query_pre_aggregated():
            start_date = datetime.utcnow().date() - timedelta(days=14)
            return DailyAnalytics.query.filter(
                DailyAnalytics.date >= start_date
            ).all()
        
        results = benchmark_query(query_pre_aggregated, 50)  # More iterations
        print(f"  Mean: {results['mean']:.2f}ms")
        print(f"  Min:  {results['min']:.2f}ms")
        print(f"  Max:  {results['max']:.2f}ms")
        print(f"  Expected with Redis: <100ms")
        
        print("\n✓ Benchmark complete")
        print("\nTarget Metrics:")
        print("  - Daily analytics query: <200ms (p95)")
        print("  - With Redis cache hit: <10ms")
        print("  - Cache hit rate target: 85%+")

if __name__ == '__main__':
    main()
```

### ✅ Phase 2 Deliverables

By end of Week 8:

1. **Redis caching layer** integrated with Flask
2. **Cache decorators** for query and result caching
3. **Query optimization** with database indexes
4. **Pre-aggregation tables** for daily analytics
5. **Response time benchmarking** showing <200ms improvements
6. **Cache invalidation strategy** for consistency

**Phase 2 Success Criteria:**
- Report loading time: 3-5s → <200ms (cache hits)
- Database query time: 2-3s → <100ms (with indexes)
- Cache hit rate: >85% for analytics endpoints
- Memory usage: No more than 2GB Redis
- Test coverage: >80%

---

## PHASE 3: Advanced NLP & ML (Weeks 9-14)

### 3.1 BERT Sentiment Analysis Model

**Objective:** Replace VADER with fine-tuned BERT for 85%+ accuracy  
**Effort:** 32 hours | **Priority:** CRITICAL

#### New File: `app/sentiment/bert_analyzer.py`

```python
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import numpy as np
from typing import Dict, Tuple

class BERTAnalyzer:
    """
    Fine-tuned BERT model for sentiment analysis
    Model: distilbert-base-uncased-finetuned-sst-2-english
    Accuracy: ~92% on SST-2 benchmark
    """
    
    def __init__(self, model_name='distilbert-base-uncased-finetuned-sst-2-english'):
        """Initialize BERT model"""
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print(f"Using device: {self.device}")
        
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()
        
        self.label_map = {0: 'Negative', 1: 'Positive'}
    
    def analyze(self, text: str) -> Dict:
        """
        Analyze sentiment using BERT
        
        Returns:
            {
                'sentiment': 'Positive' or 'Negative',
                'score': float (0-1),
                'confidence': float (0-1),
                'probabilities': {
                    'negative': float,
                    'positive': float
                }
            }
        """
        # Tokenize
        inputs = self.tokenizer(
            text,
            return_tensors='pt',
            truncation=True,
            max_length=512,
            padding=True
        ).to(self.device)
        
        # Inference
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
        
        # Convert logits to probabilities
        probs = torch.nn.functional.softmax(logits, dim=-1)
        probs_cpu = probs.cpu().numpy()[0]
        
        negative_prob = float(probs_cpu[0])
        positive_prob = float(probs_cpu[1])
        
        # Determine sentiment and score
        if positive_prob > negative_prob:
            sentiment = 'Positive'
            score = positive_prob
        else:
            sentiment = 'Negative'
            score = negative_prob
        
        confidence = max(positive_prob, negative_prob)
        
        return {
            'sentiment': sentiment,
            'score': score,
            'confidence': confidence,
            'probabilities': {
                'negative': negative_prob,
                'positive': positive_prob
            }
        }
    
    def batch_analyze(self, texts: list) -> list:
        """Analyze multiple texts at once (faster)"""
        results = []
        
        inputs = self.tokenizer(
            texts,
            return_tensors='pt',
            truncation=True,
            max_length=512,
            padding=True,
            batch_size=32
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
        
        probs = torch.nn.functional.softmax(logits, dim=-1)
        probs_cpu = probs.cpu().numpy()
        
        for i, text in enumerate(texts):
            negative_prob = float(probs_cpu[i][0])
            positive_prob = float(probs_cpu[i][1])
            
            sentiment = 'Positive' if positive_prob > negative_prob else 'Negative'
            score = max(positive_prob, negative_prob)
            
            results.append({
                'text': text,
                'sentiment': sentiment,
                'score': score,
                'confidence': score,
                'probabilities': {
                    'negative': negative_prob,
                    'positive': positive_prob
                }
            })
        
        return results
```

#### New File: `app/sentiment/ensemble.py`

```python
from app.sentiment.vader_analyzer import analyze_text as vader_analyze
from app.sentiment.bert_analyzer import BERTAnalyzer
import numpy as np

class EnsembleAnalyzer:
    """
    Ensemble model combining VADER + BERT for maximum accuracy
    - VADER: Fast, rule-based, captures emoticons and punctuation
    - BERT: Deep learning,better handles context and nuance
    """
    
    def __init__(self):
        """Initialize both models"""
        self.bert = BERTAnalyzer()
        # VADER loaded implicitly from vader_analyze
    
    def analyze(self, text: str) -> Dict:
        """
        Analyze with ensemble and return combined result
        
        Returns:
            {
                'text': str,
                'sentiment': 'Positive', 'Negative', or 'Neutral',
                'score': float (0-1),
                'confidence': float (0-1),
                'models': {
                    'vader': {...},
                    'bert': {...}
                }
            }
        """
        # Get VADER result
        vader_result = vader_analyze(text)
        
        # Get BERT result
        bert_result = self.bert.analyze(text)
        
        # Combine results with weighted ensemble
        # Weights based on empirical testing
        vader_weight = 0.3
        bert_weight = 0.7
        
        # Normalize VADER compound (-1 to 1) to (0 to 1)
        vader_normalized = (vader_result['compound_score'] + 1) / 2
        
        # Combine scores
        ensemble_score = (
            vader_normalized * vader_weight +
            bert_result['score'] * bert_weight
        )
        
        # Determine ensemble sentiment
        # VADER detects neutral, BERT only does pos/neg
        if vader_result['sentiment'] == 'Neutral':
            ensemble_sentiment = 'Neutral'
            confidence = 1 - abs(vader_result['compound_score'])
        else:
            # Use BERT's prediction as primary
            ensemble_sentiment = bert_result['sentiment']
            confidence = bert_result['confidence'] * bert_weight + \
                        (1 - abs(vader_result['compound_score']) * 0.5) * vader_weight
        
        return {
            'text': text,
            'sentiment': ensemble_sentiment,
            'score': ensemble_score,
            'confidence': min(confidence, 1.0),
            'models': {
                'vader': {
                    'sentiment': vader_result['sentiment'],
                    'score': vader_normalized,
                    'compound': vader_result['compound_score'],
                },
                'bert': {
                    'sentiment': bert_result['sentiment'],
                    'score': bert_result['score'],
                    'confidence': bert_result['confidence'],
                }
            }
        }
    
    def batch_analyze(self, texts: list) -> list:
        """Batch analyze multiple texts"""
        results = []
        
        # Get BERT results in batch (faster)
        bert_results = self.bert.batch_analyze(texts)
        
        for i, text in enumerate(texts):
            vader_result = vader_analyze(text)
            bert_result = bert_results[i]
            
            # Combine using same weights
            vader_weight = 0.3
            bert_weight = 0.7
            
            vader_normalized = (vader_result['compound_score'] + 1) / 2
            ensemble_score = (
                vader_normalized * vader_weight +
                bert_result['score'] * bert_weight
            )
            
            if vader_result['sentiment'] == 'Neutral':
                ensemble_sentiment = 'Neutral'
                confidence = 1 - abs(vader_result['compound_score'])
            else:
                ensemble_sentiment = bert_result['sentiment']
                confidence = bert_result['confidence'] * bert_weight + \
                            (1 - abs(vader_result['compound_score']) * 0.5) * vader_weight
            
            results.append({
                'text': text,
                'sentiment': ensemble_sentiment,
                'score': ensemble_score,
                'confidence': min(confidence, 1.0),
                'models': {
                    'vader': vader_result['sentiment'],
                    'bert': bert_result['sentiment'],
                }
            })
        
        return results
```

#### Model Training Setup: `app/sentiment/fine_tune_bert.py`

```python
"""
Fine-tune BERT on custom labeled dataset for your specific domain
Run once to train, then use saved model
"""

import torch
from torch.utils.data import Dataset, DataLoader
from transformers import Trainer, TrainingArguments, AutoModelForSequenceClassification, AutoTokenizer
import json

class ReviewDataset(Dataset):
    """Custom dataset for reviews"""
    
    def __init__(self, texts, labels, tokenizer, max_length=512):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length
    
    def __len__(self):
        return len(self.texts)
    
    def __getitem__(self, idx):
        text = self.texts[idx]
        label = self.labels[idx]
        
        encoding = self.tokenizer(
            text,
            max_length=self.max_length,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )
        
        return {
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten(),
            'labels': torch.tensor(label)
        }

def fine_tune_bert(train_data_path, output_dir='models/bert-fine-tuned'):
    """
    Fine-tune BERT on labeled review data
    
    Args:
        train_data_path: JSON file with format:
            [
                {"text": "Great product!", "label": 1},  # 1 = Positive
                {"text": "Terrible quality", "label": 0}  # 0 = Negative
            ]
        output_dir: Where to save fine-tuned model
    """
    
    # Load data
    with open(train_data_path) as f:
        data = json.load(f)
    
    texts = [item['text'] for item in data]
    labels = [item['label'] for item in data]
    
    # Split train/test
    split_idx = int(len(texts) * 0.8)
    train_texts, test_texts = texts[:split_idx], texts[split_idx:]
    train_labels, test_labels = labels[:split_idx], labels[split_idx:]
    
    # Prepare tokenizer and model
    model_name = 'distilbert-base-uncased'
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=2)
    
    # Create datasets
    train_dataset = ReviewDataset(train_texts, train_labels, tokenizer)
    test_dataset = ReviewDataset(test_texts, test_labels, tokenizer)
    
    # Training arguments
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=3,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=16,
        warmup_steps=500,
        weight_decay=0.01,
        logging_dir='logs',
        logging_steps=10,
        evaluation_strategy="epoch",
        save_strategy="epoch",
    )
    
    # Train
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=test_dataset,
    )
    
    trainer.train()
    
    # Save fine-tuned model
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    
    print(f"✓ Fine-tuned model saved to {output_dir}")

if __name__ == '__main__':
    # Example usage
    fine_tune_bert(
        'data/labeled_reviews.json',
        'models/bert-fine-tuned'
    )
```

### 3.2 Fake Review Detection ML Pipeline

**Objective:** Build scikit-learn ML model for 82%+ fake detection accuracy  
**Effort:** 20 hours | **Priority:** CRITICAL

#### New File: `app/ml/fake_detector.py`

```python
import pickle
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
import joblib
from typing import Dict, Tuple
import json

class FakeReviewDetector:
    """
    Machine Learning pipeline to detect fake/spam reviews
    Uses ensemble of features:
    - Textual patterns (length, repetition, capitalization)
    - Sentiment inconsistency
    - Behavioral patterns (review timing, reviewer history)
    - Content similarity to known fake reviews
    """
    
    def __init__(self, model_path=None):
        """Initialize detector"""
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = [
            'text_length',
            'avg_word_length',
            'uppercase_ratio',
            'exclamation_count',
            'repeated_chars',
            'unique_words_ratio',
            'sentiment_compound_abs',
            'sentiment_variance',
            'review_count_by_reviewer',
            'days_between_reviews',
            'similar_reviews_nearby',
        ]
        
        if model_path:
            self.load_model(model_path)
    
    def extract_features(self, review: Dict) -> np.ndarray:
        """
        Extract features from a review for prediction
        
        Args:
            review: {
                'text': str,
                'rating': float,
                'sentiment': str,
                'compound_score': float,
                'reviewer_name': str,
                'review_count': int,
                'days_since_last_review': int
            }
        
        Returns:
            Feature vector for ML model
        """
        text = review['text'].lower()
        words = text.split()
        
        features = []
        
        # 1. Text length (fake reviews often very short or very long)
        features.append(len(text))  # text_length
        
        # 2. Average word length
        avg_word_len = np.mean([len(w) for w in words]) if words else 0
        features.append(avg_word_len)  # avg_word_length
        
        # 3. Uppercase ratio (spam often has excessive caps)
        uppercase_count = sum(1 for c in text if c.isupper())
        uppercase_ratio = uppercase_count / len(text) if len(text) > 0 else 0
        features.append(uppercase_ratio)  # uppercase_ratio
        
        # 4. Exclamation count (spam markers)
        exclamation_count = text.count('!')
        features.append(exclamation_count)  # exclamation_count
        
        # 5. Repeated characters (fake reviews often repeat: "amaaaazing")
        max_repeated = 0
        current_repeated = 1
        for i in range(1, len(text)):
            if text[i] == text[i-1]:
                current_repeated += 1
            else:
                max_repeated = max(max_repeated, current_repeated)
                current_repeated = 1
        features.append(max_repeated)  # repeated_chars
        
        # 6. Unique words ratio (real reviews more diverse vocabulary)
        unique_words = len(set(words))
        unique_ratio = unique_words / len(words) if words else 0
        features.append(unique_ratio)  # unique_words_ratio
        
        # 7. Sentiment-rating inconsistency
        sentiment = review.get('sentiment', 'Neutral')
        rating = review.get('rating', 3)
        compound = review.get('compound_score', 0)
        
        # Positive review should have high rating and positive sentiment
        sentiment_inconsistency = 0
        if sentiment == 'Positive' and rating < 2:
            sentiment_inconsistency = 1
        elif sentiment == 'Negative' and rating > 4:
            sentiment_inconsistency = 1
        
        features.append(abs(compound))  # sentiment_compound_abs
        features.append(float(sentiment_inconsistency))  # sentiment_variance
        
        # 8. Reviewer history (fake reviewers have suspicious patterns)
        review_count = review.get('review_count', 1)
        # Normalize: very low of very high counts are suspicious
        normalized_count = 1 / (1 + review_count / 10)
        features.append(normalized_count)  # review_count_by_reviewer
        
        # 9. Days since last review (fake reviewers often burst)
        days_between = review.get('days_since_last_review', 30)
        # Less than 1 day or more than 365 days is suspicious
        days_suspicion = 0 if 1 <= days_between <= 365 else 1
        features.append(float(days_suspicion))  # days_between_reviews
        
        # 10. Similarity to other recent reviews (copied reviews)
        similar_reviews = review.get('similar_reviews_count', 0)
        features.append(min(similar_reviews / 5, 1.0))  # similar_reviews_nearby
        
        return np.array(features, dtype=float).reshape(1, -1)
    
    def predict(self, review: Dict) -> Dict:
        """
        Predict if review is fake
        
        Returns:
            {
                'is_fake': bool,
                'probability': float (0-1),
                'confidence': float,
                'risk_factors': [str],
                'explanation': str
            }
        """
        if self.model is None:
            raise ValueError("Model not loaded. Train model first.")
        
        features = self.extract_features(review)
        features_scaled = self.scaler.transform(features)
        
        # Probability of being fake
        probability = self.model.predict_proba(features_scaled)[0][1]
        
        is_fake = probability > 0.5
        confidence = max(probability, 1 - probability)
        
        # Identify risk factors
        risk_factors = self._identify_risk_factors(review, features)
        
        # Generate explanation
        explanation = self._generate_explanation(is_fake, probability, risk_factors)
        
        return {
            'is_fake': bool(is_fake),
            'probability': float(probability),
            'confidence': float(confidence),
            'risk_factors': risk_factors,
            'explanation': explanation,
            'features_used': self.feature_names
        }
    
    def _identify_risk_factors(self, review: Dict, features: np.ndarray) -> list:
        """Identify specific red flags"""
        factors = []
        
        text = review['text'].lower()
        
        if len(text) < 10:
            factors.append("Text too short")
        
        if len(text) > 1000:
            factors.append("Text unusually long")
        
        if text.count('!') > 5:
            factors.append("Excessive exclamation marks")
        
        if features[0, 2] > 0.3:  # uppercase_ratio
            factors.append("Excessive uppercase letters")
        
        if review.get('sentiment') == 'Positive' and review.get('rating', 3) < 2:
            factors.append("Positive text but low rating")
        
        if review.get('review_count', 1) > 50:
            factors.append("Reviewer has suspiciously many reviews")
        
        if review.get('similar_reviews_count', 0) > 3:
            factors.append("Similar to other recent reviews")
        
        return factors
    
    def _generate_explanation(self, is_fake: bool, probability: float, factors: list) -> str:
        """Generate human-readable explanation"""
        if not is_fake:
            return f"Appears to be legitimate review (confidence: {(1-probability):.1%})"
        
        if probability > 0.9:
            score = "Very likely fake"
        elif probability > 0.75:
            score = "Likely fake"
        else:
            score = "Possibly fake"
        
        factors_text = " and ".join(factors) if factors else "pattern matching"
        
        return f"{score} ({probability:.1%} confidence) due to: {factors_text}"
    
    def train(self, training_data: list, labels: np.ndarray,
              test_data: list = None, test_labels: np.ndarray = None):
        """
        Train the fake detection model
        
        Args:
            training_data: List of review dicts with full information
            labels: Binary labels (1 = fake, 0 = legitimate)
            test_data: Optional test set
            test_labels: Optional test labels
        """
        # Extract features
        X_train = np.vstack([self.extract_features(r) for r in training_data])
        
        # Scale features
        self.scaler.fit(X_train)
        X_train_scaled = self.scaler.transform(X_train)
        
        # Train ensemble model
        self.model = GradientBoostingClassifier(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            random_state=42
        )
        
        self.model.fit(X_train_scaled, labels)
        
        # Evaluate
        train_acc = self.model.score(X_train_scaled, labels)
        print(f"✓ Training accuracy: {train_acc:.2%}")
        
        if test_data is not None:
            X_test = np.vstack([self.extract_features(r) for r in test_data])
            X_test_scaled = self.scaler.transform(X_test)
            
            test_acc = self.model.score(X_test_scaled, test_labels)
            print(f"✓ Test accuracy: {test_acc:.2%}")
            
            # Additional metrics
            predictions = self.model.predict(X_test_scaled)
            print("\nClassification Report:")
            print(classification_report(test_labels, predictions))
    
    def save_model(self, path: str):
        """Save trained model"""
        joblib.dump(self.model, f'{path}/model.pkl')
        joblib.dump(self.scaler, f'{path}/scaler.pkl')
        print(f"✓ Model saved to {path}")
    
    def load_model(self, path: str):
        """Load trained model"""
        self.model = joblib.load(f'{path}/model.pkl')
        self.scaler = joblib.load(f'{path}/scaler.pkl')
        print(f"✓ Model loaded from {path}")
```

#### Training Script: `app/ml/train_fake_detector.py`

```python
"""
Train fake review detection model
Run this script to create a trained ML model from labeled data
"""

import json
import numpy as np
from app.ml.fake_detector import FakeReviewDetector
from sklearn.model_selection import train_test_split

def load_training_data(json_path):
    """Load labeled training data"""
    with open(json_path) as f:
        data = json.load(f)
    
    reviews = [item['review'] for item in data]
    labels = np.array([item['is_fake'] for item in data])  # 1 = fake, 0 = legit
    
    return reviews, labels

def train_and_save():
    """Train and save fake detector model"""
    
    # Load training data
    reviews, labels = load_training_data('data/labeled_reviews.json')
    
    # Split into train/test
    X_train, X_test, y_train, y_test = train_test_split(
        reviews, labels, test_size=0.2, random_state=42, stratify=labels
    )
    
    # Create and train detector
    detector = FakeReviewDetector()
    detector.train(X_train, y_train, X_test, y_test)
    
    # Save
    detector.save_model('models/fake_detector')
    
    print("\n✓ Model training complete!")
    print(f"Training set: {len(X_train)} reviews")
    print(f"Test set: {len(X_test)} reviews")
    print(f"Fake reviews in dataset: {labels.sum()} ({labels.sum()/len(labels):.1%})")

if __name__ == '__main__':
    train_and_save()
```

### 3.3 API Updates for Enhanced Sentiment

**Objective:** Update API to use ensemble sentiment models  
**Effort:** 4 hours | **Priority:** HIGH

Update `app/api/routes.py`:

```python
@api_bp.route('/analyze', methods=['POST'])
@jwt_required()
def analyze_reviews():
    """Enhanced analysis with BERT + fake detection"""
    from app.sentiment.ensemble import EnsembleAnalyzer
    from app.ml.fake_detector import FakeReviewDetector
    from app.core.aggregations import update_daily_analytics
    from app.cache.decorators import invalidate_cache
    
    data = request.get_json()
    query = data.get('query')
    source = data.get('source', 'google')
    user_id = get_jwt_identity()
    
    # Create analysis run
    analysis = AnalysisRun(
        user_id=user_id,
        query=query,
        source=source,
        status='running'
    )
    db.session.add(analysis)
    db.session.commit()
    
    try:
        # Scrape reviews (existing code)
        from app.scraping.scraper import scrape_reviews
        raw_reviews = scrape_reviews(query, source)
        
        # Initialize analyzers
        ensemble = EnsembleAnalyzer()
        fake_detector = FakeReviewDetector('models/fake_detector')
        
        sentiment_reviews = []
        
        for review in raw_reviews:
            # Ensemble sentiment analysis
            sentiment_data = ensemble.analyze(review['text'])
            
            # Fake review detection
            review_with_sentiment = {
                **review,
                'sentiment': sentiment_data['sentiment'],
                'compound_score': sentiment_data['score'],
            }
            fake_prediction = fake_detector.predict(review_with_sentiment)
            
            # Create review record
            record = ReviewRecord(
                analysis_run_id=analysis.id,
                text=review['text'],
                reviewer_name=review.get('reviewer_name'),
                rating=review.get('rating'),
                
                # VADER scores
                sentiment=sentiment_data['models']['vader']['sentiment'],
                compound_score=sentiment_data['models']['vader']['compound'],
                positive_score=review.get('positive_score', 0),
                negative_score=review.get('negative_score', 0),
                neutral_score=review.get('neutral_score', 0),
                
                # BERT scores
                bert_sentiment=sentiment_data['models']['bert']['sentiment'],
                bert_score=sentiment_data['models']['bert']['score'],
                bert_confidence=sentiment_data['models']['bert']['confidence'],
                
                # Ensemble result
                ensemble_sentiment=sentiment_data['sentiment'],
                ensemble_score=sentiment_data['score'],
                ensemble_confidence=sentiment_data['confidence'],
                
                # Fake detection
                is_fake=fake_prediction['is_fake'],
                fake_probability=fake_prediction['probability'],
                fake_reason=fake_prediction['explanation'],
                
                source=source,
            )
            
            db.session.add(record)
            sentiment_reviews.append(record.to_dict())
        
        # Update analysis
        analysis.status = 'completed'
        analysis.total_reviews = len(raw_reviews)
        analysis.filtered_reviews = sum(1 for r in sentiment_reviews if not r.get('is_fake'))
        analysis.completed_at = datetime.utcnow()
        
        db.session.commit()
        
        # Update daily analytics
        update_daily_analytics()
        
        # Invalidate cache
        cache.clear_pattern('analysis:*')
        
        return jsonify({
            'analysis_id': analysis.id,
            'status': analysis.status,
            'total_reviews': analysis.total_reviews,
            'filtered_reviews': analysis.filtered_reviews,
            'fake_count': analysis.total_reviews - analysis.filtered_reviews,
            'reviews': sentiment_reviews,
            'models_used': ['vader', 'bert', 'ensemble'],
            'sentiment_accuracy': 'ensemble',
        }), 200
    
    except Exception as e:
        analysis.status = 'failed'
        db.session.commit()
        
        return jsonify({'error': str(e)}), 500
```

### 3.4 Model Evaluation & Testing

**Objective:** Validate accuracy improvements  
**Effort:** 6 hours | **Priority:** HIGH

Create `tests/integration/test_sentiment_models.py`:

```python
import pytest
from app.sentiment.vader_analyzer import analyze_text as vader_analyze
from app.sentiment.bert_analyzer import BERTAnalyzer
from app.sentiment.ensemble import EnsembleAnalyzer

test_cases = [
    ("This product is absolutely amazing! I love it!", "Positive"),
    ("Terrible quality, waste of money", "Negative"),
    ("It's okay, nothing special", "Neutral"),
    ("Best purchase ever!!! Highly recommend!!!", "Positive"),
    ("Don't buy this garbage", "Negative"),
    ("The product works as described", "Neutral"),
]

@pytest.mark.slow  # May take time for GPU inference
class TestSentimentModels:
    """Test sentiment analysis models"""
    
    @pytest.fixture(scope="class")
    def bert(self):
        return BERTAnalyzer()
    
    @pytest.fixture(scope="class")
    def ensemble(self):
        return EnsembleAnalyzer()
    
    def test_vader_basic(self):
        """VADER should handle basic cases"""
        for text, expected_sentiment in test_cases[:3]:
            result = vader_analyze(text)
            assert result['sentiment'] == expected_sentiment
    
    def test_bert_analysis(self, bert):
        """BERT should classify correctly"""
        for text, expected in [
            ("This is wonderful!", "Positive"),
            ("This is horrible", "Negative"),
        ]:
            result = bert.analyze(text)
            assert result['sentiment'] == expected
            assert result['confidence'] > 0.8
    
    def test_ensemble_analysis(self, ensemble):
        """Ensemble should combine models"""
        for text, expected in test_cases[:3]:
            result = ensemble.analyze(text)
            assert result['sentiment'] in ['Positive', 'Negative', 'Neutral']
            # Ensemble should have high confidence
            assert result['confidence'] > 0.7
    
    def test_batch_performance(self, bert):
        """Batch analysis should be faster than individual"""
        texts = [t[0] for t in test_cases]
        
        import time
        
        # Single
        start = time.time()
        for text in texts:
            bert.analyze(text)
        single_time = time.time() - start
        
        # Batch
        start = time.time()
        bert.batch_analyze(texts)
        batch_time = time.time() - start
        
        # Batch should be faster
        assert batch_time < single_time * 0.7
        print(f"\nSingle: {single_time:.2f}s, Batch: {batch_time:.2f}s")
    
    def test_confidence_scores(self, ensemble):
        """Confidence should be calibrated"""
        # Clear positive
        result = ensemble.analyze("Absolutely fantastic!")
        assert result['confidence'] > 0.85
        
        # Ambiguous
        result = ensemble.analyze("It works")
        assert result['confidence'] < 0.80
```

### ✅ Phase 3 Deliverables

By end of Week 14:

1. **BERT sentiment model** with 92%+ accuracy
2. **Ensemble analyzer** combining VADER+BERT with optimized weights
3. **ML-based fake detection** with 82% precision
4. **Feature extraction pipeline** for reviewanalysis
5. **Model training scripts** for continuous improvement
6. **Updated API endpoints** with ensemble results
7. **Comprehensive testing** of all models

**Phase 3 Success Criteria:**
- Sentiment accuracy: 75% (VADER) → 85%+ (Ensemble)
- Fake detection precision: 60% → 82%
- Model inference time: <500ms per batch
- Test set F1-score: >0.82
- Business impact: <5% false negatives on training data

---

## PHASE 4: Async Processing & Scalability (Weeks 15-19)

*(Due to token limits, Phase 4-5 summary provided)*

### 4.1 Background Task Processing with Celery

Create`app/celery_app.py`:

```python
from celery import Celery
from config import Config

celery = Celery(
    __name__,
    broker=Config.CELERY_BROKER_URL,
    backend=Config.CELERY_RESULT_BACKEND
)

celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

@celery.task
def scrape_and_analyze(analysis_id):
    """Background task for scraping and analyzing reviews"""
    from app import create_app
    from app.core.models import AnalysisRun
    
    app = create_app()
    with app.app_context():
        analysis = AnalysisRun.query.get(analysis_id)
        # ... scraping and analysis logic ...
        analysis.status = 'completed'
        db.session.commit()

@celery.task
def train_fake_detector_task():
    """Background task for model retraining"""
    from app.ml.fake_detector import FakeReviewDetector
    # ... training logic ...
```

### 4.2 Kubernetes Configuration

Create `kubernetes/deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sentiment-analyzer
spec:
  replicas: 3
  selector:
    matchLabels:
      app: sentiment-analyzer
  template:
    metadata:
      labels:
        app: sentiment-analyzer
    spec:
      containers:
      - name: web
        image: sentiment-analyzer:1.0.0
        ports:
        - containerPort: 5000
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 5000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 5000
          initialDelaySeconds: 5
          periodSeconds: 5
      autoscaling:
        minReplicas: 2
        maxReplicas: 10
        targetCPUUtilizationPercentage: 70
```

---

## PHASE 5: Monitoring, Testing & Deployment (Weeks 20-24)

### 5.1 Comprehensive Logging

Create `app/logging/logger.py`:

```python
import logging
import json
from pythonjsonlogger import jsonlogger
from config import Config

def setup_logging(app):
    """Setup structured JSON logging"""
    
    if app.config['LOG_FORMAT'] == 'json':
        formatter = jsonlogger.JsonFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    
    app.logger.addHandler(handler)
    app.logger.setLevel(app.config['LOG_LEVEL'])
```

### 5.2 Production Deployment

Create `Dockerfile`:

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt requirements-ml.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-ml.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "wsgi:app"]
```

---

## Code Architecture Changes

### Current App Structure Refactoring

**Before (Current):**
```python
# app.py - Everything here (400+ lines)
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

analyzer = SentimentIntensityAnalyzer()
app = Flask(__name__)

@app.route('/analyze', methods=['POST'])
def analyze():
    # Scraping logic
    # Sentiment analysis inline
    # Database saves
    # Response building
    pass
```

**After (Modular):**
```python
# wsgi.py - Production entry point
from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run()
```

```python
# app/__init__.py - Application factory
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from app.auth.routes import auth_bp
from app.api.routes import api_bp

def create_app(config=None):
    app = Flask(__name__)
    
    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    cache.init_app(app)
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)
    
    return app
```

---

## Database Schema Evolution

### Current Schema (Phase 1+)

```sql
-- Users and authentication
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username VARCHAR(80) UNIQUE,
    email VARCHAR(120) UNIQUE,
    password_hash VARCHAR(255),
    role VARCHAR(20),
    is_active BOOLEAN,
    created_at DATETIME,
    last_login DATETIME
);

-- Review records with enhanced sentiment
CREATE TABLE review_records (
    id INTEGER PRIMARY KEY,
    analysis_run_id INTEGER,
    text TEXT,
    
    -- VADER sentiment (Phase 1)
    sentiment VARCHAR(20),
    compound_score FLOAT,
    positive_score FLOAT,
    negative_score FLOAT,
    neutral_score FLOAT,
    
    -- BERT sentiment (Phase 3)
    bert_sentiment VARCHAR(20),
    bert_score FLOAT,
    bert_confidence FLOAT,
    
    -- Ensemble (Phase 3)
    ensemble_sentiment VARCHAR(20),
    ensemble_score FLOAT,
    ensemble_confidence FLOAT,
    
    -- Fake detection (Phase 3)
    is_fake BOOLEAN,
    fake_probability FLOAT,
    fake_reason VARCHAR(255),
    
    -- Metadata
    rating FLOAT,
    source VARCHAR(50),
    created_at DATETIME,
    processed_at DATETIME
);

-- Pre-aggregated daily analytics
CREATE TABLE daily_analytics (
    id INTEGER PRIMARY KEY,
    date DATE UNIQUE,
    total_reviews INTEGER,
    positive_count INTEGER,
    negative_count INTEGER,
    neutral_count INTEGER,
    fake_count INTEGER,
    avg_compound_score FLOAT,
    bert_avg_score FLOAT,
    ensemble_avg_score FLOAT,
    fake_detection_rate FLOAT,
    created_at DATETIME
);
```

---

## Deployment Architecture

### Local Development Stack (docker-compose)

```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "5000:5000"
    environment:
      - FLASK_ENV=development
      - DATABASE_URL=postgresql://user:password@db:5432/sentiment
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
      - celery

  db:
    image: postgres:13
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=sentiment
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:6-alpine
    ports:
      - "6379:6379"

  celery:
    build: .
    command: celery -A app.celery_app worker -l info
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/1
    depends_on:
      - redis

  celery-beat:
    build: .
    command: celery -A app.celery_app beat -l info
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/1
    depends_on:
      - redis

volumes:
  postgres_data:
```

### Production Deployment (Kubernetes)

Components:
- **Web Service**: Gunicorn + Flask (3 replicas, auto-scaling)
- **PostgreSQL**: Managed database (CloudSQL, Aurora)
- **Redis**: In-memory cache (ElastiCache, Redis Enterprise)
- **Celery Workers**: Background tasks (2-5 replicas)
- **Monitoring**: Prometheus + Grafana
- **Logging**: ELK Stack (Elasticsearch, Logstash, Kibana)

---

## Success Metrics & KPIs

### Technical Metrics

| Metric | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 |
|--------|---------|---------|---------|---------|---------|
| **API Response Time (p95)** | 500ms | 300ms | 250ms | 250ms | <200ms |
| **Report Load Time** | 3-5s | <500ms | <400ms | <300ms | <200ms |
| **Sentiment Accuracy** | 75% | 75% | 85%+ | 85%+ | 85% |
| **Fake Detection Precision** | N/A | N/A | 82%+ | 82%+ | 82% |
| **Cache Hit Rate** | 0% | 75%+ | 80%+ | 85%+ | 85%+ |
| **Test Coverage** | 60% | 75% | 82% | 85% | 90%+ |
| **Uptime** | N/A | N/A | N/A | 99.5% | 99.9% |

### Business Metrics

- **User Adoption**: 0 (MVP) → 100+ active users (Phase 5)
- **Requests/Day**: 0 → 10,000+ (Phase 5)
- **Data Volume**: <1GB → 50GB+ (Phase 5)
- **Cost/Request**: $0.10 → $0.001 (Phase 5)
- **Mean Time to Recovery**: N/A → <30 minutes (Phase 5)

---

## Risk Mitigation

### Critical Dependencies

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| BERT model training takes too long | Medium | High | Use pre-trained models, reduce training data |
| Redis memory issues | Low | High | Implement cache eviction policy, monitoring |
| Database migration failures | Low | Critical | Backup before migration, test on staging |
| Celery task deadlocks | Medium | Medium | Implement timeouts, dead letter queues |
| GPU availability for inference | Low | High | Fallback to CPU, use quantization |

### Monitoring & Alerts

Set up alerts for:
- API latency >1 second
- Error rate >1%
- Cache hit rate <70%
- Database query >5 seconds
- Celery queue backlog >100 tasks
- Memory usage >80%
- Disk space <20%

---

## Next Steps (Immediate Action Items)

**Week 1-4 (Phase 1) Priority:**

1. ✅ Create project structure
2. ✅ Implement JWT authentication
3. ✅ Update database models
4. ✅ Write 80%+ unit tests
5. Run full test suite: `pytest tests/ -v --cov=app --cov-report=html`
6. Deploy to staging environment

**Communication Plan:**

Send stakeholders:
- Weekly progress reports
- Challenges and blockers
- Budget and timeline tracking
- Demo of completed features

---

**End of Detailed Implementation Plan**

*This document should be reviewed quarterly and updated based on actual progress and emerging requirements.*

