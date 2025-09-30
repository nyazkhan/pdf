#!/usr/bin/env python3
"""
Start the FastAPI backend server
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Check for API key
if not os.getenv("GEMINI_API_KEY"):
    print("⚠️  Warning: GEMINI_API_KEY not set. AI features will be limited.")
else:
    print("✅ Gemini API key loaded successfully")

# Import and run the API
from src.api.main import app
import uvicorn

if __name__ == "__main__":
    print("🚀 Starting PDF Accessibility API Server")
    print("=" * 50)
    print("📍 API Documentation: http://localhost:8000/docs")
    print("🔄 WebSocket: ws://localhost:8000/ws/{session_id}")
    print("=" * 50)
    
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )