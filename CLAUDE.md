# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## PDF Accessibility Web Application

This is a web-based PDF accessibility analysis and remediation tool with a React frontend and FastAPI backend.

## Development Commands

### Backend API
```bash
# Install dependencies  
pip install -r requirements.txt

# Start FastAPI backend server
python start_api.py

# Or directly with uvicorn
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# API endpoints available at:
# - http://localhost:8000 (REST API)
# - http://localhost:8000/docs (Swagger documentation)
# - ws://localhost:8000/ws/{session_id} (WebSocket)
```

### Frontend (React)
```bash
# Navigate to frontend directory
cd pdf-accessibility-frontend

# Install dependencies (first time)
npm install

# Start development server
npm start
# Opens at http://localhost:3000

# Build for production
npm run build

# Run tests
npm test
```

### Testing Components
```bash
# Test PDF parsing on specific file
python -m src.core.pdf_parser path/to/test.pdf

# Test accessibility rules
python -m src.core.accessibility_rules --wcag-level AA

# Test AI alt text generation
python -m src.ai.alt_text_generator path/to/image.png

# Test visual integrity
python test_visual_integrity.py path/to/test.pdf

# Enable debug logging
LOG_LEVEL=DEBUG python start_api.py
```

## Architecture Overview

This is a web-based PDF accessibility analysis and remediation tool with the following architecture:

### Core Processing Pipeline
```
PDF Upload → PDFParser → WCAGValidator → FixManager → PDFWriter → Accessible PDF
```

The application uses **invisible fixes mode** by default to preserve visual PDF integrity while adding accessibility metadata.

### Component Structure

**API Layer (FastAPI)**: `src/api/main.py` provides REST endpoints for PDF analysis, AI suggestions, and fixes. Includes WebSocket support for real-time updates during processing.

**Core Engine**: 
- `pdf_parser.py`: Extracts 12+ PDF element types
- `accessibility_rules.py`: Implements all 23 W3C PDF accessibility techniques (PDF1-PDF23)
- `fix_manager.py`: Tracks applied fixes and maintains session state
- `report_manager.py`: Handles persistence to SQLite database and JSON exports

**AI Integration**: 
- `AccessibilityAIAgent`: Coordinates AI enhancements
- `AltTextGenerator`: Uses BLIP-2 vision models with lazy loading
- `gemini_client.py`: Gemini AI integration for advanced suggestions

**PDF Processing**: `pdf_writer.py` applies fixes using PyMuPDF while preserving visual integrity.

## Key Configuration Files

### config.yaml Structure
```yaml
accessibility:
  wcag_level: "AA"        # Controls validation strictness
  auto_fix: []           # List of auto-applicable fix types

ai_models:
  vision_model: "Salesforce/blip-image-captioning-base"
  device: "cpu"          # Set to "cuda" for GPU acceleration

pdf_processing:
  max_pages: 500         # Performance limit
  batch_size: 10         # Concurrent processing limit
```

### Environment Variables
- `GEMINI_API_KEY`: Required for Gemini AI features
- `LOG_LEVEL`: Set to DEBUG for verbose logging

## Development Patterns

### Session Management
The system maintains session state through `FixManager` and persists to both JSON and SQLite formats. Session files track applied fixes, issue states, and user interactions for resumability.

### Error Handling Strategy
The application implements graceful degradation:
- AI features disable if models unavailable
- PDF processing continues with basic fixes if advanced features fail
- Detailed error logging helps with debugging

### API Authentication
The API includes JWT-based authentication and rate limiting:
- API keys stored in `api_keys_db`
- Different rate limits for analysis, AI, and export endpoints
- Usage tracking per API key

## Important Implementation Details

### Visual Integrity Preservation
The `invisible_fixes` mode was implemented to solve user-reported visual corruption. Fixes are applied through:
- Metadata insertion
- Structure tree modifications  
- Hidden text annotations
- Accessibility tags without visual markers

### WCAG Compliance Implementation
`accessibility_rules.py` implements comprehensive validation:
- All 23 PDF accessibility techniques from W3C specification
- WCAG 2.1/2.2 Level A/AA/AAA compliance checking
- Detailed remediation guidance for each issue type
- Integration with PDF/UA standards

### AI Model Management  
- Models download automatically on first run (~200-500MB)
- Cached in user's home directory
- Support for both CPU and GPU inference
- Timeout handling for slow model loading

## Performance Considerations

- Large PDFs (>50MB): Process during low system usage
- AI model inference: Significant memory usage (1-2GB)
- First startup: 5-10 minutes for model downloads
- Typical processing: 10-30 seconds for small PDFs, 2-5 minutes for large ones
- Batch processing: Preferred for multiple similar files

## Frontend Technologies

The React frontend uses:
- Material-UI for components
- PDF.js for PDF rendering
- Socket.io for real-time updates
- React Query for API state management
- TypeScript for type safety

# Important Instructions
- Focus on web-based functionality only
- Do not reference or implement desktop GUI features
- Prioritize API and React frontend development
- Always preserve visual PDF integrity when applying fixes