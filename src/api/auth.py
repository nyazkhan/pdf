#!/usr/bin/env python3
"""
Authentication and rate limiting for PDF Accessibility API
"""

import os
import time
import hashlib
import secrets
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict

from fastapi import HTTPException, Security, Depends, Request
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import jwt

# Configuration
SECRET_KEY = os.getenv("API_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
API_KEY_HEADER_NAME = "X-API-Key"

# Rate limiting configuration
RATE_LIMITS = {
    "default": {"requests": 100, "window": 60},  # 100 requests per minute
    "analyze": {"requests": 10, "window": 60},    # 10 PDF analyses per minute
    "ai": {"requests": 50, "window": 60},         # 50 AI requests per minute
    "export": {"requests": 20, "window": 60},     # 20 exports per minute
}

# In-memory storage for demo (use Redis in production)
api_keys_db: Dict[str, Dict[str, Any]] = {
    "demo_key_123": {
        "name": "Demo User",
        "email": "demo@example.com",
        "tier": "free",
        "created_at": datetime.now().isoformat()
    }
}

rate_limiter_data = defaultdict(lambda: defaultdict(list))

# Security schemes
api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class ApiKeyInfo(BaseModel):
    api_key: str
    name: str
    email: str
    tier: str
    created_at: str

# JWT Token Management
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[dict]:
    """Verify JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# API Key Authentication
async def get_api_key(api_key: str = Security(api_key_header)) -> str:
    """Validate API key"""
    if api_key is None:
        raise HTTPException(
            status_code=403,
            detail="API Key required. Include X-API-Key header"
        )
    
    if api_key not in api_keys_db:
        raise HTTPException(
            status_code=403,
            detail="Invalid API Key"
        )
    
    return api_key

# Bearer Token Authentication
async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)) -> dict:
    """Get current user from bearer token"""
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )
    
    token = credentials.credentials
    payload = verify_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials"
        )
    
    return payload

# Rate Limiting
class RateLimiter:
    """Rate limiting implementation"""
    
    def __init__(self, requests: int = 100, window: int = 60):
        self.requests = requests
        self.window = window
    
    async def __call__(self, request: Request, api_key: str = Depends(get_api_key)):
        """Check rate limit for API key"""
        client_id = f"{api_key}:{request.client.host}"
        endpoint = request.url.path
        current_time = time.time()
        
        # Clean old entries
        rate_limiter_data[client_id][endpoint] = [
            timestamp for timestamp in rate_limiter_data[client_id][endpoint]
            if current_time - timestamp < self.window
        ]
        
        # Check rate limit
        if len(rate_limiter_data[client_id][endpoint]) >= self.requests:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Max {self.requests} requests per {self.window} seconds",
                headers={"Retry-After": str(self.window)}
            )
        
        # Record request
        rate_limiter_data[client_id][endpoint].append(current_time)
        return api_key

# Create rate limiters for different endpoints
default_limiter = RateLimiter(**RATE_LIMITS["default"])
analyze_limiter = RateLimiter(**RATE_LIMITS["analyze"])
ai_limiter = RateLimiter(**RATE_LIMITS["ai"])
export_limiter = RateLimiter(**RATE_LIMITS["export"])

# API Key Management Functions
def generate_api_key() -> str:
    """Generate a new API key"""
    return f"pdf_ak_{secrets.token_urlsafe(32)}"

def hash_api_key(api_key: str) -> str:
    """Hash API key for storage"""
    return hashlib.sha256(api_key.encode()).hexdigest()

def create_api_key(name: str, email: str, tier: str = "free") -> ApiKeyInfo:
    """Create a new API key"""
    api_key = generate_api_key()
    
    # Store API key (in production, store hashed version)
    api_keys_db[api_key] = {
        "name": name,
        "email": email,
        "tier": tier,
        "created_at": datetime.now().isoformat()
    }
    
    return ApiKeyInfo(
        api_key=api_key,
        name=name,
        email=email,
        tier=tier,
        created_at=api_keys_db[api_key]["created_at"]
    )

def revoke_api_key(api_key: str) -> bool:
    """Revoke an API key"""
    if api_key in api_keys_db:
        del api_keys_db[api_key]
        return True
    return False

# Usage Tracking
class UsageTracker:
    """Track API usage for billing/analytics"""
    
    def __init__(self):
        self.usage_data = defaultdict(lambda: {
            "requests": 0,
            "pdf_pages": 0,
            "ai_calls": 0,
            "export_count": 0
        })
    
    def track_request(self, api_key: str, endpoint: str):
        """Track API request"""
        self.usage_data[api_key]["requests"] += 1
    
    def track_pdf_analysis(self, api_key: str, pages: int):
        """Track PDF analysis"""
        self.usage_data[api_key]["pdf_pages"] += pages
    
    def track_ai_call(self, api_key: str):
        """Track AI API call"""
        self.usage_data[api_key]["ai_calls"] += 1
    
    def track_export(self, api_key: str):
        """Track report export"""
        self.usage_data[api_key]["export_count"] += 1
    
    def get_usage(self, api_key: str) -> dict:
        """Get usage statistics for API key"""
        return dict(self.usage_data.get(api_key, {}))

# Initialize usage tracker
usage_tracker = UsageTracker()

# Tier-based limits
TIER_LIMITS = {
    "free": {
        "daily_pdfs": 10,
        "max_pdf_size": 10 * 1024 * 1024,  # 10MB
        "ai_calls": 100,
        "concurrent_sessions": 1
    },
    "pro": {
        "daily_pdfs": 100,
        "max_pdf_size": 50 * 1024 * 1024,  # 50MB
        "ai_calls": 1000,
        "concurrent_sessions": 5
    },
    "enterprise": {
        "daily_pdfs": -1,  # Unlimited
        "max_pdf_size": 200 * 1024 * 1024,  # 200MB
        "ai_calls": -1,  # Unlimited
        "concurrent_sessions": -1  # Unlimited
    }
}

def check_tier_limit(api_key: str, limit_type: str, value: int = 1) -> bool:
    """Check if user is within tier limits"""
    user_info = api_keys_db.get(api_key)
    if not user_info:
        return False
    
    tier = user_info.get("tier", "free")
    limits = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
    
    limit = limits.get(limit_type, 0)
    if limit == -1:  # Unlimited
        return True
    
    # Check against current usage
    usage = usage_tracker.get_usage(api_key)
    
    if limit_type == "daily_pdfs":
        return usage.get("pdf_pages", 0) + value <= limit
    elif limit_type == "ai_calls":
        return usage.get("ai_calls", 0) + value <= limit
    
    return True

# Middleware for request tracking
async def track_request_middleware(request: Request, api_key: str = Depends(get_api_key)):
    """Middleware to track all API requests"""
    usage_tracker.track_request(api_key, request.url.path)
    return api_key