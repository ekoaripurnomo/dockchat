# Specification-Driven Development Document
## Chat-Controlled Docker Container Management with AI-Powered Project Scaffolding

**Version:** 2.2  
**Date:** September 7, 2026  
**Status:** Ready for Implementation

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Overview](#2-system-overview)
3. [User Authentication & Management](#3-user-authentication--management)
4. [LLM Model Selection & Configuration](#4-llm-model-selection--configuration)
5. [AI Provider Management](#5-ai-provider-management)
6. [Base Image Catalog System](#6-base-image-catalog-system)
7. [Project Analysis Engine](#7-project-analysis-engine)
8. [Dockerfile Generation Logic](#8-dockerfile-generation-logic)
9. [Enhanced Architecture](#9-enhanced-architecture)
10. [Tool Definitions & Functions](#10-tool-definitions--functions)
11. [Chat Flow & User Interaction](#11-chat-flow--user-interaction)
12. [Implementation Stack](#12-implementation-stack)
13. [Development Phases](#13-development-phases)
14. [Testing Strategy](#14-testing-strategy)
15. [Security Considerations](#15-security-considerations)
16. [Performance Optimization](#16-performance-optimization)
17. [Monitoring & Observability](#17-monitoring--observability)
18. [Resource Requirements](#18-resource-requirements)
19. [Future Enhancements](#19-future-enhancements)
20. [Appendices](#20-appendices)

---

## 1. Executive Summary

This document specifies the architecture and implementation plan for an AI-powered chat application that enables users to create, manage, and deploy Docker containers through natural language conversation. The system includes **multi-tenant user authentication and management**, allowing individual users to have personalized workspaces, container configurations, and project history.

The system leverages **vLLM** as the inference engine with the ability to **switch between local inference and OpenAI-compatible API providers** through a configuration menu. The application incorporates advanced project scaffolding capabilities, allowing users to:

- **Chat naturally** with an AI assistant about Docker operations
- **Analyze existing projects** and generate appropriate Docker configurations
- **Select from curated base images** with intelligent suggestions
- **Generate production-ready Dockerfiles** and docker-compose.yml files
- **Manage the full container lifecycle** through conversational interaction
- **Switch AI providers** dynamically between local vLLM and external APIs
- **Configure model parameters** (temperature, max tokens, top_p) per user session
- **Create user accounts** with personalized workspaces
- **Secure authentication** with JWT tokens and role-based access control

---

## 2. System Overview

### 2.1 Core Concept

Users interact with a chat interface, issuing natural language commands such as:
- "Create a PostgreSQL container with persistent storage"
- "Open my project at /home/user/my-app and prepare Docker configuration"
- "Deploy a full-stack application with React frontend and Node.js backend"
- "Generate a Dockerfile for my Python Flask application"
- "Switch to GPT-4 for better code generation"
- "Save this container configuration as 'production-stack'"

The LLM interprets these requests, validates the intent, performs necessary analysis, generates appropriate Docker configurations, and executes them safely. The system supports multiple AI providers with seamless switching and includes complete user management with authentication.

### 2.2 Key Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Chat Interface** | Streamlit or Gradio | User-facing conversational UI with file browser |
| **User Authentication** | JWT, OAuth2 | Secure login, registration, session management |
| **User Database** | PostgreSQL | Store user profiles, preferences, configurations |
| **AI Provider Manager** | Factory Pattern | Manages multiple AI provider connections |
| **LLM Backend** | vLLM / OpenAI / Azure / Anthropic | Model serving and inference |
| **Model Brain** | Qwen3-14B / GPT-4 / Claude | Intent parsing, Docker command generation |
| **Project Analyzer** | Python with AST parsing | Detect project type, dependencies, structure |
| **Docker Orchestrator** | Docker SDK for Python | Container management, image building |
| **Dockerfile Generator** | Jinja2 templating | Generate optimized Dockerfiles |
| **Conversation Memory** | Redis | Chat history, session management |
| **API Layer** | FastAPI | REST endpoints, WebSocket for streaming |
| **MCP Integration** | Docker MCP Gateway | Standardized tool calling interface |
| **Configuration Manager** | Pydantic | Manage AI provider settings and credentials |
| **Workspace Manager** | File System | Per-user project directories and configurations |

### 2.3 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         User Chat Interface                                     │
│                    (Streamlit / Gradio + File Browser)                          │
│                    🔐 Login/Register | ⚙️ AI Provider Menu                    │
└────────────────────────┬────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     FastAPI Application                                         │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                    Authentication Middleware                              │  │
│  │  - JWT Validation - Role Check - Session Management                     │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                    Orchestration Engine                                   │  │
│  │  - Intent Parser  - Project Analyzer  - Dockerfile Generator            │  │
│  │  - Safety Checker - Base Image Selector  - Volume Manager              │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                         │                                                      │
│         ┌───────────────┼───────────────┬───────────┬─────────────┬─────────┐ │
│         ▼               ▼               ▼           ▼             ▼         │ │
│  ┌───────────┐  ┌────────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │   Redis   │  │  AI        │  │  Docker  │  │  Image   │  │   Users   │  │
│  │  Session  │  │ Provider   │  │   SDK    │  │ Registry │  │  Database │  │
│  │  Memory   │  │  Manager   │  │          │  │ Catalog  │  │ (Postgres)│  │
│  └───────────┘  └────────────┘  └──────────┘  └──────────┘  └───────────┘  │
│                         │                                                      │
│         ┌───────────────┼───────────────┬──────────────┬────────────────────┐ │
│         ▼               ▼               ▼              ▼                    │ │
│  ┌────────────┐  ┌───────────┐  ┌────────────┐  ┌──────────┐  ┌──────────┐ │
│  │   vLLM     │  │  OpenAI   │  │   Azure    │  │ Anthropic│  │ User     │ │
│  │  (Local)   │  │  GPT-4    │  │  OpenAI    │  │  Claude  │  │ Workspace│ │
│  └────────────┘  └───────────┘  └────────────┘  └──────────┘  └──────────┘ │
│                         │                                                      │
│         ┌───────────────┴───────────────┐                                    │
│         ▼                               ▼                                    │
│  ┌─────────────────┐           ┌─────────────────┐                          │
│  │  File System    │           │  Docker MCP     │                          │
│  │  Scanner        │           │  Server         │                          │
│  └─────────────────┘           └─────────────────┘                          │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. User Authentication & Management

### 3.1 User Database Schema

```sql
-- PostgreSQL User Schema
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    email_verified BOOLEAN DEFAULT FALSE,
    verification_token VARCHAR(255),
    reset_password_token VARCHAR(255),
    reset_password_expires TIMESTAMP
);

CREATE TABLE user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    default_provider VARCHAR(50) DEFAULT 'vllm',
    default_model_params JSONB DEFAULT '{"temperature": 0.7, "max_tokens": 4096}',
    default_base_image VARCHAR(100),
    default_project_path VARCHAR(500),
    theme VARCHAR(20) DEFAULT 'dark',
    notifications_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id)
);

CREATE TABLE user_workspaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    path VARCHAR(500) NOT NULL,
    description TEXT,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(500) NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    revoked_at TIMESTAMP,
    UNIQUE(token)
);

CREATE TABLE user_containers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    container_id VARCHAR(100),
    name VARCHAR(100),
    image VARCHAR(200),
    status VARCHAR(50),
    configuration JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE user_projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    path VARCHAR(500) NOT NULL,
    project_type VARCHAR(50),
    dockerfile_path VARCHAR(500),
    compose_path VARCHAR(500),
    configuration JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(100),
    details JSONB,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_sessions_token ON user_sessions(token);
CREATE INDEX idx_sessions_expires ON user_sessions(expires_at);
CREATE INDEX idx_containers_user ON user_containers(user_id);
CREATE INDEX idx_projects_user ON user_projects(user_id);
CREATE INDEX idx_audit_user ON audit_logs(user_id);
CREATE INDEX idx_audit_created ON audit_logs(created_at);
```

### 3.2 User Authentication Models

```python
# backend/models/user.py
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from datetime import datetime, timedelta
import bcrypt
import jwt
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None
    
    @validator('username')
    def validate_username(cls, v):
        if not v.isalnum() and '_' not in v:
            raise ValueError('Username must be alphanumeric or contain underscores')
        return v
    
    @validator('password')
    def validate_password(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one number')
        return v

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: UUID
    username: str
    email: str
    full_name: Optional[str]
    created_at: datetime
    last_login: Optional[datetime]
    is_active: bool
    is_superuser: bool
    preferences: Optional[Dict[str, Any]]
    workspaces: Optional[List[Dict[str, Any]]]

class UserUpdate(BaseModel):
    full_name: Optional[str]
    email: Optional[EmailStr]
    password: Optional[str]
    preferences: Optional[Dict[str, Any]]

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    user: UserResponse

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)
```

### 3.3 User Service Implementation

```python
# backend/services/user_service.py
import bcrypt
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import UUID
import asyncpg
from fastapi import HTTPException, status

class UserService:
    def __init__(self, db_pool: asyncpg.Pool, config: Dict[str, Any]):
        self.db_pool = db_pool
        self.jwt_secret = config["jwt_secret"]
        self.jwt_algorithm = config.get("jwt_algorithm", "HS256")
        self.access_token_expire = config.get("access_token_expire", 3600)
        self.refresh_token_expire = config.get("refresh_token_expire", 86400 * 7)
    
    async def create_user(self, user_data: UserCreate) -> UserResponse:
        """Create a new user account"""
        # Check if user exists
        async with self.db_pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT id FROM users WHERE username = $1 OR email = $2",
                user_data.username, user_data.email
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username or email already registered"
                )
            
            # Hash password
            password_hash = bcrypt.hashpw(
                user_data.password.encode('utf-8'),
                bcrypt.gensalt()
            ).decode('utf-8')
            
            # Create user
            user_id = uuid4()
            await conn.execute(
                """
                INSERT INTO users (id, username, email, password_hash, full_name)
                VALUES ($1, $2, $3, $4, $5)
                """,
                user_id, user_data.username, user_data.email,
                password_hash, user_data.full_name
            )
            
            # Create default preferences
            await conn.execute(
                """
                INSERT INTO user_preferences (user_id)
                VALUES ($1)
                """,
                user_id
            )
            
            # Create default workspace
            default_path = f"/workspace/{user_data.username}"
            await conn.execute(
                """
                INSERT INTO user_workspaces (user_id, name, path, is_default)
                VALUES ($1, $2, $3, TRUE)
                """,
                user_id, "default", default_path
            )
            
            # Return user
            return await self.get_user_by_id(user_id)
    
    async def authenticate_user(self, username: str, password: str) -> Optional[UserResponse]:
        """Authenticate user credentials"""
        async with self.db_pool.acquire() as conn:
            user = await conn.fetchrow(
                """
                SELECT id, username, email, password_hash, full_name,
                       created_at, last_login, is_active, is_superuser
                FROM users
                WHERE username = $1 AND is_active = TRUE
                """,
                username
            )
            
            if not user:
                return None
            
            # Verify password
            if not bcrypt.checkpw(
                password.encode('utf-8'),
                user['password_hash'].encode('utf-8')
            ):
                return None
            
            # Update last login
            await conn.execute(
                "UPDATE users SET last_login = NOW() WHERE id = $1",
                user['id']
            )
            
            # Get preferences
            prefs = await conn.fetchrow(
                "SELECT * FROM user_preferences WHERE user_id = $1",
                user['id']
            )
            
            return UserResponse(
                id=user['id'],
                username=user['username'],
                email=user['email'],
                full_name=user['full_name'],
                created_at=user['created_at'],
                last_login=user['last_login'],
                is_active=user['is_active'],
                is_superuser=user['is_superuser'],
                preferences=dict(prefs) if prefs else None
            )
    
    async def get_user_by_id(self, user_id: UUID) -> Optional[UserResponse]:
        """Get user by ID"""
        async with self.db_pool.acquire() as conn:
            user = await conn.fetchrow(
                """
                SELECT id, username, email, full_name,
                       created_at, last_login, is_active, is_superuser
                FROM users
                WHERE id = $1
                """,
                user_id
            )
            
            if not user:
                return None
            
            prefs = await conn.fetchrow(
                "SELECT * FROM user_preferences WHERE user_id = $1",
                user_id
            )
            
            return UserResponse(
                id=user['id'],
                username=user['username'],
                email=user['email'],
                full_name=user['full_name'],
                created_at=user['created_at'],
                last_login=user['last_login'],
                is_active=user['is_active'],
                is_superuser=user['is_superuser'],
                preferences=dict(prefs) if prefs else None
            )
    
    async def create_token(self, user_id: UUID) -> TokenResponse:
        """Create JWT tokens for user"""
        # Get user
        user = await self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Create access token
        access_token = jwt.encode(
            {
                "sub": str(user_id),
                "username": user.username,
                "role": "user",
                "exp": datetime.utcnow() + timedelta(seconds=self.access_token_expire)
            },
            self.jwt_secret,
            algorithm=self.jwt_algorithm
        )
        
        # Create refresh token
        refresh_token = jwt.encode(
            {
                "sub": str(user_id),
                "type": "refresh",
                "exp": datetime.utcnow() + timedelta(seconds=self.refresh_token_expire)
            },
            self.jwt_secret,
            algorithm=self.jwt_algorithm
        )
        
        # Store refresh token in database
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_sessions (user_id, token, expires_at)
                VALUES ($1, $2, NOW() + INTERVAL '7 days')
                """,
                user_id, refresh_token
            )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=user
        )
    
    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        """Refresh access token using refresh token"""
        try:
            payload = jwt.decode(
                refresh_token,
                self.jwt_secret,
                algorithms=[self.jwt_algorithm]
            )
            
            if payload.get("type") != "refresh":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type"
                )
            
            user_id = UUID(payload["sub"])
            
            # Check if token exists and is not revoked
            async with self.db_pool.acquire() as conn:
                session = await conn.fetchrow(
                    """
                    SELECT id FROM user_sessions
                    WHERE token = $1 AND revoked_at IS NULL AND expires_at > NOW()
                    """,
                    refresh_token
                )
                
                if not session:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid or expired refresh token"
                    )
            
            # Create new tokens
            return await self.create_token(user_id)
            
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
    
    async def revoke_token(self, refresh_token: str):
        """Revoke a refresh token (logout)"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE user_sessions
                SET revoked_at = NOW()
                WHERE token = $1
                """,
                refresh_token
            )
    
    async def revoke_all_tokens(self, user_id: UUID):
        """Revoke all tokens for a user"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE user_sessions
                SET revoked_at = NOW()
                WHERE user_id = $1
                """,
                user_id
            )
    
    async def update_user(self, user_id: UUID, updates: UserUpdate) -> UserResponse:
        """Update user information"""
        async with self.db_pool.acquire() as conn:
            updates_dict = updates.dict(exclude_unset=True)
            
            if "password" in updates_dict:
                password_hash = bcrypt.hashpw(
                    updates_dict["password"].encode('utf-8'),
                    bcrypt.gensalt()
                ).decode('utf-8')
                updates_dict["password_hash"] = password_hash
                del updates_dict["password"]
            
            if "preferences" in updates_dict:
                prefs = updates_dict.pop("preferences")
                await conn.execute(
                    """
                    UPDATE user_preferences
                    SET default_provider = $1,
                        default_model_params = $2,
                        default_base_image = $3,
                        theme = $4,
                        updated_at = NOW()
                    WHERE user_id = $5
                    """,
                    prefs.get("default_provider"),
                    prefs.get("default_model_params"),
                    prefs.get("default_base_image"),
                    prefs.get("theme"),
                    user_id
                )
            
            if updates_dict:
                set_clause = ", ".join([f"{k} = ${i+1}" for i, k in enumerate(updates_dict.keys())])
                values = list(updates_dict.values()) + [user_id]
                await conn.execute(
                    f"""
                    UPDATE users
                    SET {set_clause}, updated_at = NOW()
                    WHERE id = ${len(values)}
                    """,
                    *values
                )
            
            return await self.get_user_by_id(user_id)
```

### 3.4 Authentication Middleware

```python
# backend/middleware/auth.py
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any
import jwt
from uuid import UUID

class AuthMiddleware(HTTPBearer):
    """Authentication middleware for FastAPI"""
    
    def __init__(self, jwt_secret: str, algorithm: str = "HS256"):
        super().__init__(auto_error=False)
        self.jwt_secret = jwt_secret
        self.algorithm = algorithm
    
    async def __call__(self, request: Request) -> Optional[Dict[str, Any]]:
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)
        
        if not credentials:
            # Allow unauthenticated requests to public endpoints
            if self._is_public_endpoint(request.url.path):
                return None
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        try:
            # Verify token
            payload = jwt.decode(
                credentials.credentials,
                self.jwt_secret,
                algorithms=[self.algorithm]
            )
            
            # Add user info to request state
            request.state.user_id = UUID(payload["sub"])
            request.state.username = payload.get("username")
            request.state.role = payload.get("role", "user")
            
            return {
                "user_id": request.state.user_id,
                "username": request.state.username,
                "role": request.state.role
            }
            
        except jwt.PyJWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    def _is_public_endpoint(self, path: str) -> bool:
        """Check if endpoint is public"""
        public_paths = [
            "/api/auth/login",
            "/api/auth/register",
            "/api/auth/refresh",
            "/api/auth/forgot-password",
            "/api/auth/reset-password",
            "/api/health",
            "/api/docs",
            "/api/openapi.json",
            "/api/redoc"
        ]
        return any(path.startswith(p) for p in public_paths)

# Dependency for getting current user
from fastapi import Depends

async def get_current_user(request: Request) -> Dict[str, Any]:
    """Get current authenticated user from request state"""
    if not hasattr(request.state, "user_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return {
        "user_id": request.state.user_id,
        "username": request.state.username,
        "role": request.state.role
    }

async def get_admin_user(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Check if current user is admin"""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user
```

### 3.5 Authentication Routes

```python
# backend/routes/auth.py
from fastapi import APIRouter, Request, Depends, HTTPException, status
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/api/auth", tags=["authentication"])

@router.post("/register", response_model=TokenResponse)
async def register(
    user_data: UserCreate,
    user_service: UserService = Depends(get_user_service)
):
    """Register a new user"""
    try:
        user = await user_service.create_user(user_data)
        return await user_service.create_token(user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: UserLogin,
    user_service: UserService = Depends(get_user_service)
):
    """Login user and return access token"""
    user = await user_service.authenticate_user(
        login_data.username,
        login_data.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    return await user_service.create_token(user.id)

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str,
    user_service: UserService = Depends(get_user_service)
):
    """Refresh access token"""
    return await user_service.refresh_token(refresh_token)

@router.post("/logout")
async def logout(
    refresh_token: str,
    user_service: UserService = Depends(get_user_service)
):
    """Logout user - revoke refresh token"""
    await user_service.revoke_token(refresh_token)
    return {"message": "Successfully logged out"}

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: Dict = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service)
):
    """Get current user information"""
    user = await user_service.get_user_by_id(current_user["user_id"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

@router.put("/me", response_model=UserResponse)
async def update_current_user(
    updates: UserUpdate,
    current_user: Dict = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service)
):
    """Update current user information"""
    return await user_service.update_user(current_user["user_id"], updates)

@router.post("/change-password")
async def change_password(
    old_password: str,
    new_password: str,
    current_user: Dict = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service)
):
    """Change user password"""
    # Verify old password
    user = await user_service.authenticate_user(
        current_user["username"],
        old_password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid current password"
        )
    
    # Update password
    updates = UserUpdate(password=new_password)
    await user_service.update_user(current_user["user_id"], updates)
    return {"message": "Password updated successfully"}

@router.post("/forgot-password")
async def forgot_password(
    request: PasswordResetRequest,
    user_service: UserService = Depends(get_user_service)
):
    """Request password reset"""
    # Generate reset token and send email
    token = await user_service.create_password_reset_token(request.email)
    await send_reset_email(request.email, token)
    return {"message": "Password reset email sent"}

@router.post("/reset-password")
async def reset_password(
    reset_data: PasswordResetConfirm,
    user_service: UserService = Depends(get_user_service)
):
    """Reset password with token"""
    user = await user_service.reset_password(
        reset_data.token,
        reset_data.new_password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    return {"message": "Password reset successfully"}
```

---

## 4. LLM Model Selection & Configuration

### 4.1 Supported AI Providers

| Provider | Models | API Type | Key Features |
|----------|--------|----------|--------------|
| **vLLM (Local)** | Qwen3-14B, GLM-4.7-Flash, Qwen3-4B | OpenAI-Compatible | Local, private, no cost |
| **OpenAI** | GPT-4, GPT-4 Turbo, GPT-3.5-Turbo | OpenAI API | Best quality, fastest |
| **Azure OpenAI** | GPT-4, GPT-3.5-Turbo | Azure API | Enterprise, compliance |
| **Anthropic** | Claude 3.5 Sonnet, Claude 3 Opus | Anthropic API | Strong reasoning |
| **Groq** | Llama3-70B, Mixtral-8x7B | Groq API | Fastest inference |
| **Together AI** | Llama3, Mistral, Qwen | Together API | Wide model selection |

### 4.2 AI Provider Configuration Schema

```python
# config/ai_providers.py
from pydantic import BaseModel, Field, SecretStr
from typing import Optional, Dict, Any, List
from enum import Enum

class ProviderType(str, Enum):
    VLLM = "vllm"
    OPENAI = "openai"
    AZURE = "azure"
    ANTHROPIC = "anthropic"
    GROQ = "groq"
    TOGETHER = "together"

class ModelCapability(str, Enum):
    TOOL_CALLING = "tool_calling"
    STREAMING = "streaming"
    FUNCTION_CALLING = "function_calling"
    JSON_MODE = "json_mode"

class AIProviderConfig(BaseModel):
    """Base configuration for AI providers"""
    provider_type: ProviderType
    name: str = Field(description="Display name")
    enabled: bool = True
    is_default: bool = False
    model: str = Field(description="Model identifier")
    api_key: Optional[SecretStr] = None
    base_url: Optional[str] = None
    organization: Optional[str] = None
    timeout: int = 60
    max_retries: int = 3
    
    # Model parameters
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(4096, ge=1, le=32000)
    top_p: float = Field(0.95, ge=0.0, le=1.0)
    
    # Capabilities
    capabilities: List[ModelCapability] = []
    
    # Provider-specific settings
    provider_settings: Dict[str, Any] = Field(default_factory=dict)
```

---

## 5. AI Provider Manager

### 5.1 Provider Manager with User-Specific Configurations

```python
# backend/services/ai_provider_manager.py
import asyncio
from typing import Optional, Dict, List
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from groq import AsyncGroq
import httpx

class AIProviderManager:
    """Manages multiple AI provider connections with user-specific configurations"""
    
    def __init__(self):
        self.global_providers: Dict[str, AIProviderConfig] = {}
        self.user_providers: Dict[str, Dict[str, AIProviderConfig]] = {}
        self.clients: Dict[str, Any] = {}
        self.active_providers: Dict[str, str] = {}
        self._lock = asyncio.Lock()
    
    def register_provider(self, config: AIProviderConfig, user_id: Optional[str] = None) -> None:
        """Register a provider configuration for a user or globally"""
        if user_id:
            if user_id not in self.user_providers:
                self.user_providers[user_id] = {}
            self.user_providers[user_id][config.name] = config
            if config.is_default:
                self.active_providers[user_id] = config.name
        else:
            self.global_providers[config.name] = config
            if config.is_default and user_id not in self.active_providers:
                self.active_providers[user_id] = config.name
    
    def get_provider(self, name: str, user_id: Optional[str] = None) -> Optional[AIProviderConfig]:
        """Get provider configuration for a user or globally"""
        if user_id and user_id in self.user_providers:
            if name in self.user_providers[user_id]:
                return self.user_providers[user_id][name]
        return self.global_providers.get(name)
    
    def list_providers(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all providers available to a user"""
        providers = []
        
        # Add global providers
        for p in self.global_providers.values():
            providers.append(self._format_provider(p))
        
        # Add user-specific providers
        if user_id and user_id in self.user_providers:
            for p in self.user_providers[user_id].values():
                providers.append(self._format_provider(p))
        
        return providers
    
    def _format_provider(self, config: AIProviderConfig) -> Dict[str, Any]:
        return {
            "name": config.name,
            "provider_type": config.provider_type.value,
            "model": config.model,
            "enabled": config.enabled,
            "is_default": config.is_default,
            "capabilities": [c.value for c in config.capabilities]
        }
    
    async def get_client(self, provider_name: Optional[str] = None, user_id: Optional[str] = None) -> Any:
        """Get or create client for a provider"""
        name = provider_name or self.active_providers.get(user_id)
        if not name:
            # Fallback to global default
            name = next((p for p in self.global_providers.values() if p.is_default), None)
            if not name:
                raise ValueError("No active provider set")
            name = name.name
        
        config = self.get_provider(name, user_id)
        if not config:
            raise ValueError(f"Provider '{name}' not found")
        
        if not config.enabled:
            raise ValueError(f"Provider '{name}' is disabled")
        
        # Return cached client if exists
        cache_key = f"{user_id}:{name}" if user_id else name
        if cache_key in self.clients:
            return self.clients[cache_key]
        
        # Create new client based on provider type
        client = await self._create_client(config)
        self.clients[cache_key] = client
        return client
    
    async def _create_client(self, config: AIProviderConfig):
        """Create provider-specific client"""
        if config.provider_type == ProviderType.VLLM:
            return AsyncOpenAI(
                base_url=config.base_url,
                api_key="EMPTY",
                timeout=config.timeout,
                max_retries=config.max_retries
            )
        elif config.provider_type == ProviderType.OPENAI:
            return AsyncOpenAI(
                api_key=config.api_key.get_secret_value() if config.api_key else None,
                base_url=config.base_url,
                timeout=config.timeout,
                max_retries=config.max_retries
            )
        elif config.provider_type == ProviderType.ANTHROPIC:
            return AsyncAnthropic(
                api_key=config.api_key.get_secret_value() if config.api_key else None,
                base_url=config.base_url,
                timeout=config.timeout,
                max_retries=config.max_retries
            )
        # ... other providers
    
    async def switch_provider(self, name: str, user_id: Optional[str] = None) -> bool:
        """Switch to a different provider for a user"""
        async with self._lock:
            config = self.get_provider(name, user_id)
            if not config or not config.enabled:
                return False
            self.active_providers[user_id] = name
            return True
```

---

## 6. API Routes with Authentication

### 6.1 Protected Routes

```python
# backend/routes/docker.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any

router = APIRouter(prefix="/api/docker", tags=["docker"])

@router.post("/containers")
async def create_container(
    request: CreateContainerRequest,
    current_user: Dict = Depends(get_current_user),
    docker_service: DockerService = Depends(get_docker_service)
):
    """Create a new container (authenticated)"""
    # Ensure container is associated with user
    container = await docker_service.create_container(
        request,
        user_id=current_user["user_id"]
    )
    # Log action
    await log_audit(
        user_id=current_user["user_id"],
        action="create_container",
        resource_id=container.id,
        details=request.dict()
    )
    return container

@router.get("/containers")
async def list_containers(
    current_user: Dict = Depends(get_current_user),
    docker_service: DockerService = Depends(get_docker_service)
):
    """List user's containers"""
    return await docker_service.list_containers(current_user["user_id"])

@router.get("/projects")
async def list_projects(
    current_user: Dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service)
):
    """List user's projects"""
    return await project_service.list_projects(current_user["user_id"])

@router.post("/projects/analyze")
async def analyze_project(
    request: ProjectAnalysisRequest,
    current_user: Dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service)
):
    """Analyze a project directory"""
    # Validate user has access to path
    if not await project_service.validate_user_path(
        current_user["user_id"],
        request.path
    ):
        raise HTTPException(
            status_code=403,
            detail="Access denied to this path"
        )
    return await project_service.analyze_project(request.path)

@router.post("/projects/generate-dockerfile")
async def generate_dockerfile(
    request: DockerfileGenerationRequest,
    current_user: Dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service)
):
    """Generate Dockerfile for a project"""
    return await project_service.generate_dockerfile(
        request,
        user_id=current_user["user_id"]
    )
```

### 6.2 Audit Logging

```python
# backend/services/audit_service.py
from typing import Dict, Any, Optional
from datetime import datetime
import asyncpg

class AuditService:
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
    
    async def log_action(
        self,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log user action to audit trail"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO audit_logs (
                    user_id, action, resource_type, resource_id,
                    details, ip_address, user_agent
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                user_id, action, resource_type, resource_id,
                details, ip_address, user_agent
            )
    
    async def get_user_audit_logs(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get audit logs for a user"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM audit_logs
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                user_id, limit, offset
            )
            return [dict(row) for row in rows]
```

---

## 7. User Interface Components

### 7.1 Login/Registration UI

```python
# frontend/components/Auth.py
import streamlit as st
import requests
from typing import Optional

class AuthManager:
    """Streamlit UI component for user authentication"""
    
    def __init__(self, api_base_url: str):
        self.api_base_url = api_base_url
        self.session = requests.Session()
    
    def render(self) -> Optional[Dict[str, str]]:
        """Render authentication UI"""
        
        # Check if already authenticated
        if st.session_state.get("authenticated", False):
            return self._render_authenticated()
        else:
            return self._render_login_register()
    
    def _render_login_register(self):
        """Render login/register forms"""
        
        # Tab selection
        tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])
        
        with tab1:
            st.header("Login")
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            
            if st.button("Login", type="primary"):
                if username and password:
                    result = self._login(username, password)
                    if result:
                        return result
                else:
                    st.error("Please fill in all fields")
        
        with tab2:
            st.header("Create Account")
            username = st.text_input("Username", key="reg_username")
            email = st.text_input("Email", key="reg_email")
            password = st.text_input("Password", type="password", key="reg_password")
            confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm")
            
            if st.button("Register", type="primary"):
                if all([username, email, password, confirm_password]):
                    if password != confirm_password:
                        st.error("Passwords do not match")
                    elif len(password) < 8:
                        st.error("Password must be at least 8 characters")
                    else:
                        result = self._register(username, email, password)
                        if result:
                            st.success("Registration successful! Please login.")
                else:
                    st.error("Please fill in all fields")
        
        return None
    
    def _login(self, username: str, password: str) -> Optional[Dict[str, str]]:
        """Handle login API call"""
        try:
            response = self.session.post(
                f"{self.api_base_url}/api/auth/login",
                json={"username": username, "password": password}
            )
            
            if response.status_code == 200:
                data = response.json()
                st.session_state.authenticated = True
                st.session_state.access_token = data["access_token"]
                st.session_state.refresh_token = data["refresh_token"]
                st.session_state.user = data["user"]
                st.session_state.username = username
                st.rerun()
                return data["user"]
            else:
                st.error("Invalid username or password")
                return None
                
        except Exception as e:
            st.error(f"Login failed: {str(e)}")
            return None
    
    def _register(self, username: str, email: str, password: str) -> Optional[Dict]:
        """Handle registration API call"""
        try:
            response = self.session.post(
                f"{self.api_base_url}/api/auth/register",
                json={
                    "username": username,
                    "email": email,
                    "password": password,
                    "full_name": username
                }
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                st.error(response.json().get("detail", "Registration failed"))
                return None
                
        except Exception as e:
            st.error(f"Registration failed: {str(e)}")
            return None
    
    def _render_authenticated(self):
        """Render authenticated user header"""
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.success(f"✅ Logged in as: **{st.session_state.username}**")
        
        with col2:
            if st.button("🚪 Logout"):
                self._logout()
                st.rerun()
        
        return None
    
    def _logout(self):
        """Handle logout"""
        try:
            refresh_token = st.session_state.get("refresh_token")
            if refresh_token:
                self.session.post(
                    f"{self.api_base_url}/api/auth/logout",
                    params={"refresh_token": refresh_token}
                )
        except:
            pass
        
        # Clear session
        st.session_state.authenticated = False
        st.session_state.access_token = None
        st.session_state.refresh_token = None
        st.session_state.user = None
        st.session_state.username = None
```

### 7.2 User Profile & Preferences UI

```python
# frontend/components/UserProfile.py
import streamlit as st
import requests

class UserProfileManager:
    """User profile and preferences UI"""
    
    def __init__(self, api_base_url: str):
        self.api_base_url = api_base_url
    
    def render(self):
        """Render user profile page"""
        st.header("👤 User Profile")
        
        if not st.session_state.get("authenticated", False):
            st.warning("Please login to access your profile")
            return
        
        # Get user data
        user = st.session_state.user
        
        # Tabs for different sections
        tab1, tab2, tab3, tab4 = st.tabs([
            "📋 Profile",
            "⚙️ Preferences",
            "📁 Workspaces",
            "📊 Activity"
        ])
        
        with tab1:
            self._render_profile(user)
        
        with tab2:
            self._render_preferences(user)
        
        with tab3:
            self._render_workspaces(user)
        
        with tab4:
            self._render_activity_logs()
    
    def _render_profile(self, user: Dict):
        """Render profile information"""
        with st.form("profile_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                username = st.text_input("Username", value=user["username"], disabled=True)
                email = st.text_input("Email", value=user["email"])
                full_name = st.text_input("Full Name", value=user.get("full_name", ""))
            
            with col2:
                created_at = st.text_input("Member Since", value=user["created_at"][:10], disabled=True)
                last_login = st.text_input("Last Login", value=user.get("last_login", "Never"), disabled=True)
                is_active = st.checkbox("Active", value=user["is_active"], disabled=True)
            
            if st.form_submit_button("Update Profile", type="primary"):
                # API call to update profile
                pass
        
        # Password change
        with st.expander("🔑 Change Password"):
            self._render_password_change()
    
    def _render_preferences(self, user: Dict):
        """Render user preferences"""
        prefs = user.get("preferences", {})
        
        col1, col2 = st.columns(2)
        
        with col1:
            default_provider = st.selectbox(
                "Default AI Provider",
                options=["vllm", "openai", "azure", "anthropic", "groq"],
                index=["vllm", "openai", "azure", "anthropic", "groq"].index(
                    prefs.get("default_provider", "vllm")
                )
            )
            
            default_base_image = st.selectbox(
                "Default Base Image",
                options=["node:20-alpine", "python:3.11-slim", "ubuntu:22.04"],
                index=0
            )
        
        with col2:
            theme = st.selectbox(
                "Theme",
                options=["dark", "light", "system"],
                index=["dark", "light", "system"].index(prefs.get("theme", "dark"))
            )
            
            notifications = st.checkbox(
                "Enable Notifications",
                value=prefs.get("notifications_enabled", True)
            )
        
        temperature = st.slider(
            "Default Temperature",
            min_value=0.0,
            max_value=2.0,
            value=prefs.get("default_model_params", {}).get("temperature", 0.7),
            step=0.1
        )
        
        max_tokens = st.slider(
            "Default Max Tokens",
            min_value=100,
            max_value=32000,
            value=prefs.get("default_model_params", {}).get("max_tokens", 4096),
            step=100
        )
        
        if st.button("Save Preferences", type="primary"):
            # API call to update preferences
            pass
    
    def _render_workspaces(self, user: Dict):
        """Render user workspaces"""
        workspaces = user.get("workspaces", [])
        
        st.subheader("Your Workspaces")
        
        for ws in workspaces:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.markdown(f"**{ws['name']}**")
                st.caption(f"Path: {ws['path']}")
                if ws.get("is_default"):
                    st.caption("⭐ Default Workspace")
            with col2:
                if ws.get("is_default"):
                    st.button("✅ Default", key=f"default_{ws['id']}", disabled=True)
                else:
                    if st.button("Set Default", key=f"set_default_{ws['id']}"):
                        # API call to set default
                        pass
            with col3:
                st.button("🗑️", key=f"delete_{ws['id']}")
        
        # Add new workspace
        with st.expander("➕ Add New Workspace"):
            name = st.text_input("Workspace Name")
            path = st.text_input("Path")
            description = st.text_area("Description")
            
            if st.button("Create Workspace", type="primary"):
                # API call to create workspace
                pass
    
    def _render_activity_logs(self):
        """Render user activity logs"""
        st.subheader("Recent Activity")
        
        # Fetch and display audit logs
        logs = self._fetch_activity_logs()
        
        for log in logs[:20]:
            with st.container():
                col1, col2 = st.columns([1, 3])
                with col1:
                    st.caption(log["created_at"][:16])
                with col2:
                    st.markdown(f"**{log['action']}** - {log.get('resource_type', '')} {log.get('resource_id', '')}")
                    if log.get("details"):
                        with st.expander("Details"):
                            st.json(log["details"])
                st.divider()
    
    def _fetch_activity_logs(self) -> List[Dict]:
        """Fetch activity logs from API"""
        try:
            response = requests.get(
                f"{self.api_base_url}/api/audit/logs",
                headers={"Authorization": f"Bearer {st.session_state.access_token}"}
            )
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return []
```

### 7.3 AI Provider Configuration UI

```python
# frontend/components/AIConfig.py
import streamlit as st
from typing import Dict, Any, Optional

class AIConfigManager:
    """AI Provider Configuration UI with user-specific settings"""
    
    def __init__(self, api_base_url: str):
        self.api_base_url = api_base_url
    
    def render(self):
        """Render AI provider configuration"""
        
        if not st.session_state.get("authenticated", False):
            st.warning("Please login to configure AI providers")
            return
        
        st.sidebar.markdown("---")
        st.sidebar.header("🤖 AI Configuration")
        
        # Get available providers
        providers = self._fetch_providers()
        current_provider = self._fetch_current_provider()
        
        if not providers:
            st.sidebar.warning("No AI providers available")
            return
        
        # Provider selection
        provider_names = [p["name"] for p in providers]
        current_index = 0
        if current_provider and current_provider["name"] in provider_names:
            current_index = provider_names.index(current_provider["name"])
        
        selected = st.sidebar.selectbox(
            "AI Provider",
            options=provider_names,
            index=current_index,
            help="Select the AI model to power your Docker assistant"
        )
        
        if selected != (current_provider["name"] if current_provider else None):
            self._switch_provider(selected)
            st.sidebar.success(f"Switched to {selected}")
            st.rerun()
        
        # Provider details
        config = self._get_provider_config(selected)
        if config:
            with st.sidebar.expander("⚙️ Model Parameters", expanded=False):
                self._render_parameters(config)
            
            with st.sidebar.expander("🔌 Connection Status", expanded=False):
                self._render_status(config)
    
    def _render_parameters(self, config: Dict[str, Any]):
        """Render model parameter controls"""
        col1, col2 = st.columns(2)
        
        with col1:
            temperature = st.slider(
                "Temperature",
                min_value=0.0,
                max_value=2.0,
                value=config.get("temperature", 0.7),
                step=0.1,
                help="Higher = more creative, lower = more focused"
            )
        
        with col2:
            max_tokens = st.slider(
                "Max Tokens",
                min_value=100,
                max_value=32000,
                value=config.get("max_tokens", 4096),
                step=100,
                help="Maximum length of response"
            )
        
        top_p = st.slider(
            "Top P",
            min_value=0.0,
            max_value=1.0,
            value=config.get("top_p", 0.95),
            step=0.05,
            help="Nucleus sampling parameter"
        )
        
        if st.button("Apply Parameters", type="primary"):
            self._update_parameters(selected, {
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p
            })
            st.success("Parameters updated!")
    
    def _render_status(self, config: Dict[str, Any]):
        """Render connection status"""
        status_col1, status_col2 = st.columns(2)
        
        with status_col1:
            if st.button("🔄 Test Connection"):
                with st.spinner("Testing..."):
                    result = self._test_connection(config["name"])
                    if result:
                        st.success("✅ Connected")
                    else:
                        st.error("❌ Connection failed")
        
        with status_col2:
            st.metric(
                "Status",
                "Active" if config.get("enabled", True) else "Disabled"
            )
    
    def _fetch_providers(self) -> List[Dict[str, Any]]:
        """Fetch available providers from API"""
        try:
            import requests
            response = requests.get(
                f"{self.api_base_url}/api/config/providers",
                headers={"Authorization": f"Bearer {st.session_state.access_token}"}
            )
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return []
    
    def _fetch_current_provider(self) -> Optional[Dict[str, Any]]:
        """Fetch current active provider"""
        try:
            import requests
            response = requests.get(
                f"{self.api_base_url}/api/config/providers/current",
                headers={"Authorization": f"Bearer {st.session_state.access_token}"}
            )
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None
    
    def _switch_provider(self, name: str) -> bool:
        """Switch to a different provider"""
        try:
            import requests
            response = requests.post(
                f"{self.api_base_url}/api/config/providers/switch",
                json={"provider_name": name},
                headers={"Authorization": f"Bearer {st.session_state.access_token}"}
            )
            return response.status_code == 200
        except:
            return False
    
    def _test_connection(self, name: str) -> bool:
        """Test connection to provider"""
        try:
            import requests
            response = requests.get(
                f"{self.api_base_url}/api/config/providers/{name}/test",
                headers={"Authorization": f"Bearer {st.session_state.access_token}"}
            )
            return response.status_code == 200 and response.json().get("connected", False)
        except:
            return False
    
    def _update_parameters(self, name: str, params: Dict[str, Any]) -> bool:
        """Update provider parameters"""
        try:
            import requests
            response = requests.put(
                f"{self.api_base_url}/api/config/providers/{name}/parameters",
                json=params,
                headers={"Authorization": f"Bearer {st.session_state.access_token}"}
            )
            return response.status_code == 200
        except:
            return False
```

---

## 8. Complete Implementation Stack

### 8.1 Backend Requirements

```txt
# requirements.txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
pydantic-settings==2.1.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6
asyncpg==0.29.0
redis==5.0.1
docker==6.1.3
openai==1.3.0
anthropic==0.7.0
groq==0.3.0
httpx==0.25.1
jinja2==3.1.2
python-dotenv==1.0.0
alembic==1.12.1
prometheus-client==0.19.0
```

### 8.2 Frontend Requirements

```txt
# frontend/requirements.txt
streamlit==1.28.0
requests==2.31.0
plotly==5.18.0
pandas==2.1.3
python-dotenv==1.0.0
```

### 8.3 Environment Configuration

```env
# .env
APP_NAME="Docker AI Assistant"
APP_VERSION="2.2.0"
DEBUG=false

# JWT Configuration
JWT_SECRET="your-secret-key-change-in-production"
JWT_ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

# Database
DATABASE_URL="postgresql://user:password@localhost:5432/dockerai"
REDIS_URL="redis://localhost:6379/0"

# AI Providers
VLLM_URL="http://localhost:8000/v1"
OPENAI_API_KEY="sk-..."
ANTHROPIC_API_KEY="sk-ant-..."
GROQ_API_KEY="gsk_..."

# Docker
DOCKER_HOST="unix:///var/run/docker.sock"
ALLOWED_PATHS="/home/user/projects:/workspace"

# Security
ALLOWED_ORIGINS="http://localhost:8501,http://localhost:3000"
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=60
```

---

## 9. Development Phases

### Phase 1: Foundation (Week 1-2)
- [ ] Set up PostgreSQL database with user schema
- [ ] Implement JWT authentication
- [ ] Create user registration and login APIs
- [ ] Build user session management
- [ ] Implement password hashing and security

### Phase 2: User Features (Week 3-4)
- [ ] User profile management
- [ ] Password reset functionality
- [ ] Email verification
- [ ] User preferences and settings
- [ ] Workspace management

### Phase 3: AI Integration (Week 5-6)
- [ ] AI provider manager with user-specific configs
- [ ] vLLM integration with authentication
- [ ] OpenAI, Anthropic, Groq providers
- [ ] Dynamic provider switching
- [ ] Provider connection testing

### Phase 4: Docker & Project Features (Week 7-8)
- [ ] Docker orchestration with user isolation
- [ ] Project analysis and detection
- [ ] Dockerfile generation
- [ ] Multi-service compose generation
- [ ] Container lifecycle management

### Phase 5: UI & Integration (Week 9-10)
- [ ] Login/Registration UI
- [ ] User profile dashboard
- [ ] AI configuration UI
- [ ] Project browser with authentication
- [ ] Chat interface with user context

### Phase 6: Security & Monitoring (Week 11-12)
- [ ] Audit logging
- [ ] Rate limiting
- [ ] Role-based access control
- [ ] Security testing
- [ ] Performance optimization
- [ ] Deployment and CI/CD

---

## 10. Security Considerations

### 10.1 Security Checklist

- [ ] **Password Security**
  - [ ] bcrypt hashing with salt rounds
  - [ ] Minimum 8 characters with complexity requirements
  - [ ] Password reset with expiration tokens
  
- [ ] **JWT Security**
  - [ ] Short-lived access tokens (15-60 minutes)
  - [ ] Refresh token rotation
  - [ ] Token revocation on logout
  
- [ ] **User Isolation**
  - [ ] Per-user workspace directories
  - [ ] Container isolation by user
  - [ ] No cross-user access
  
- [ ] **API Security**
  - [ ] Rate limiting per user
  - [ ] CORS configuration
  - [ ] Input validation and sanitization
  
- [ ] **Data Protection**
  - [ ] Encryption at rest
  - [ ] TLS in production
  - [ ] No sensitive data in logs

### 10.2 Security Middleware

```python
# backend/middleware/security.py
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Any
import time

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware per user"""
    
    def __init__(self, app, redis_client, requests_per_minute: int = 60):
        super().__init__(app)
        self.redis = redis_client
        self.requests_per_minute = requests_per_minute
    
    async def dispatch(self, request: Request, call_next):
        # Get user ID from request state
        user_id = getattr(request.state, "user_id", "anonymous")
        
        # Check rate limit
        key = f"rate_limit:{user_id}:{time.time() // 60}"
        current = await self.redis.incr(key)
        if current == 1:
            await self.redis.expire(key, 60)
        
        if current > self.requests_per_minute:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please try again later."
            )
        
        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(
            self.requests_per_minute - current
        )
        return response

class AuditMiddleware(BaseHTTPMiddleware):
    """Audit logging middleware"""
    
    async def dispatch(self, request: Request, call_next):
        # Record request start
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Log if authenticated
        if hasattr(request.state, "user_id"):
            duration = (time.time() - start_time) * 1000
            await self.log_request(
                user_id=request.state.user_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration
            )
        
        return response
```

---

## 11. Conclusion

This enhanced specification transforms the chat app into a complete multi-tenant platform with:

1. **Secure User Authentication** - JWT-based with refresh tokens and password reset
2. **User Management** - Registration, profiles, preferences, and workspaces
3. **Isolated Workspaces** - Per-user directories and container configurations
4. **Personalized AI Settings** - User-specific provider preferences and model parameters
5. **Audit Trail** - Complete logging of all user actions
6. **Scalable Architecture** - Multi-tenant design supporting multiple users

The system provides a complete solution for teams and organizations to collaborate on Docker container management with personalized AI assistance, secure access control, and comprehensive auditing capabilities.

---

## 12. Appendices

### Appendix A: Database Migration Scripts

```sql
-- migrations/001_initial_schema.sql
-- Complete schema available in Section 3.1
```

### Appendix B: API Documentation

Swagger UI available at `/api/docs` (authenticated)

### Appendix C: Deployment Guide

See [DEPLOYMENT.md](DEPLOYMENT.md) for production deployment instructions.

### Appendix D: Security Audit Checklist

Complete security audit checklist in [SECURITY.md](SECURITY.md).

### Appendix E: User Guide

End-user documentation in [USER_GUIDE.md](USER_GUIDE.md).
