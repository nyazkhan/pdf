#!/usr/bin/env python3
"""
FastAPI Backend for PDF Accessibility Tool
Provides REST endpoints for PDF analysis, AI suggestions, fixes, and validation
"""

import os
import sys
import json
import uuid
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import tempfile
import shutil

# FastAPI imports
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, WebSocket, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
import uvicorn
import aiofiles

# Import authentication
from src.api.auth import (
    get_api_key, get_current_user, 
    default_limiter, analyze_limiter, ai_limiter, export_limiter,
    usage_tracker, check_tier_limit, create_api_key, Token, create_access_token,
    api_keys_db
)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import PDF accessibility components
from src.core.pdf_parser import PDFParser
from src.core.accessibility_rules import WCAGValidator
from src.core.fix_manager import FixManager
from src.utils.pdf_writer import PDFWriter
from src.core.tag_tree_schema import AccessibilityTagTree, DocumentMetadata
from src.core.verapdf_validator import VeraPDFValidator
from src.ai.agent import AccessibilityAIAgent
from src.core.html_report_generator import HTMLReportGenerator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="PDF Accessibility API",
    description="AI-powered PDF accessibility analysis and remediation",
    version="1.0.0"
)

# Configure CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Storage for active sessions
active_sessions: Dict[str, Dict] = {}
upload_dir = Path("./uploads")
upload_dir.mkdir(exist_ok=True)

# Initialize AI agent globally
ai_agent = AccessibilityAIAgent()
verapdf_validator = VeraPDFValidator()

# WebSocket connections for real-time updates
websocket_connections: Dict[str, WebSocket] = {}

# Pydantic models for request/response
class AnalyzeRequest(BaseModel):
    file_path: Optional[str] = None  # Can be filename or full path
    session_id: Optional[str] = None  # Alternative: use session from upload
    wcag_level: str = "AA"
    include_ai_suggestions: bool = True

class AnalyzeResponse(BaseModel):
    session_id: str
    tag_tree: Dict
    issues: List[Dict]
    metadata: Dict
    ai_available: bool
    processing_time: float

class AISuggestRequest(BaseModel):
    session_id: str
    elements: List[Dict]
    context: Optional[str] = None

class AIAltTextRequest(BaseModel):
    session_id: str
    image_data: str  # Base64 encoded
    context: Optional[str] = ""
    page_number: Optional[int] = None

class FixRequest(BaseModel):
    session_id: str
    fixes: List[Dict]
    apply_invisible: bool = True
    create_backup: bool = True

class ValidateRequest(BaseModel):
    session_id: str
    profile: str = "PDFUA_1"  # PDF/UA-1, PDFUA_2, WCAG21_AA

# Utility functions
async def save_upload_file(upload_file: UploadFile) -> str:
    """Save uploaded file and return path"""
    file_id = str(uuid.uuid4())
    file_path = upload_dir / f"{file_id}_{upload_file.filename}"
    
    async with aiofiles.open(file_path, 'wb') as f:
        content = await upload_file.read()
        await f.write(content)
    
    return str(file_path)

async def notify_websocket(session_id: str, message: Dict):
    """Send real-time update via WebSocket"""
    if session_id in websocket_connections:
        try:
            await websocket_connections[session_id].send_json(message)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            del websocket_connections[session_id]

# REST Endpoints

@app.post("/api/upload", dependencies=[Depends(default_limiter)])
async def upload_pdf(file: UploadFile = File(...), api_key: str = Depends(get_api_key)):
    """Upload PDF file for processing"""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    try:
        file_path = await save_upload_file(file)
        session_id = str(uuid.uuid4())
        
        active_sessions[session_id] = {
            "file_path": file_path,
            "filename": file.filename,
            "created_at": datetime.now().isoformat(),
            "status": "uploaded"
        }
        
        return {
            "session_id": session_id,
            "filename": file.filename,
            "file_path": file_path,
            "message": "File uploaded successfully"
        }
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def build_accessibility_tag_tree(analysis: Dict, metadata: DocumentMetadata) -> AccessibilityTagTree:
    """Build AccessibilityTagTree from analysis results"""
    from src.core.tag_tree_schema import AccessibilityNode, NodeType, NodeStatus, BoundingBox
    
    tree = AccessibilityTagTree(metadata)
    
    # Add headings to tree
    for heading in analysis.get('headings', []):
        level = heading.metadata.get('level', 1)
        # Map level to appropriate NodeType
        heading_type = getattr(NodeType, f'H{level}', NodeType.H1)
        
        node = AccessibilityNode(
            id=f"heading_{heading.page_num}_{id(heading)}",
            type=heading_type,
            page=heading.page_num,
            bbox=BoundingBox(*heading.bbox) if heading.bbox else BoundingBox(0, 0, 0, 0),
            status=NodeStatus.OK,
            text=heading.content
        )
        tree.add_node("doc-root", node)
    
    # Add text blocks
    for text_block in analysis.get('text_blocks', []):
        node = AccessibilityNode(
            id=f"text_{text_block.page_num}_{id(text_block)}",
            type=NodeType.P,
            page=text_block.page_num,
            bbox=BoundingBox(*text_block.bbox) if text_block.bbox else BoundingBox(0, 0, 0, 0),
            status=NodeStatus.OK,
            text=text_block.content
        )
        tree.add_node("doc-root", node)
    
    # Add images
    for image in analysis.get('images', []):
        node = AccessibilityNode(
            id=f"image_{image.page_num}_{image.image_id}",
            type=NodeType.FIGURE,
            page=image.page_num,
            bbox=BoundingBox(*image.bbox) if image.bbox else BoundingBox(0, 0, 0, 0),
            status=NodeStatus.ERROR if not image.alt_text else NodeStatus.OK,
            text=image.alt_text or "",
            alt_text=image.alt_text
        )
        tree.add_node("doc-root", node)
    
    return tree

def find_uploaded_file(filename: str) -> str:
    """Find uploaded file by filename in uploads directory"""
    uploads_dir = Path("./uploads")
    
    # First try exact match
    if (uploads_dir / filename).exists():
        return str(uploads_dir / filename)
    
    # Then try with session prefix pattern
    for file in uploads_dir.glob(f"*_{filename}"):
        return str(file)
    
    raise HTTPException(status_code=404, detail=f"File not found: {filename}")

@app.post("/api/analyze", response_model=AnalyzeResponse, dependencies=[Depends(analyze_limiter)])
async def analyze_pdf(request: AnalyzeRequest, background_tasks: BackgroundTasks, api_key: str = Depends(get_api_key)):
    """Extract accessibility tags and issues from PDF"""
    import time
    start_time = time.time()
    
    try:
        # Determine file path based on input
        if request.session_id:
            # Use session to get file path
            if request.session_id not in active_sessions:
                raise HTTPException(status_code=404, detail="Session not found")
            file_path = active_sessions[request.session_id]["file_path"]
        elif request.file_path:
            # Check if it's a full path or just filename
            if os.path.exists(request.file_path):
                file_path = request.file_path
            else:
                # Try to find the file in uploads
                file_path = find_uploaded_file(request.file_path)
        else:
            raise HTTPException(status_code=400, detail="Either file_path or session_id must be provided")
        
        logger.info(f"Analyzing PDF: {file_path}")
        
        # Parse PDF and get complete analysis
        parser = PDFParser(file_path)
        analysis = parser.analyze_document()
        
        # Clean analysis data - convert PyMuPDF Rect objects to tuples
        def clean_rect(obj):
            """Recursively convert PyMuPDF Rect objects to tuples"""
            import fitz
            if isinstance(obj, fitz.Rect):
                return tuple(obj)
            elif isinstance(obj, dict):
                return {k: clean_rect(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [clean_rect(item) for item in obj]
            elif hasattr(obj, '__dict__'):
                # Handle objects with attributes
                cleaned = {}
                for attr in ['bbox', 'rect']:
                    if hasattr(obj, attr):
                        val = getattr(obj, attr)
                        if isinstance(val, fitz.Rect):
                            setattr(obj, attr, tuple(val))
                return obj
            return obj
        
        analysis = clean_rect(analysis)
        
        # Create tag tree from analysis
        metadata = DocumentMetadata(
            title=analysis['metadata'].get('title', 'Untitled'),
            language=analysis.get('document_language', 'en-US'),
            pages=analysis['total_pages']
        )
        tag_tree = build_accessibility_tag_tree(analysis, metadata)
        
        # Run WCAG validation
        validator = WCAGValidator(wcag_level=request.wcag_level)
        issues = validator.validate_document(analysis)
        
        # Get AI suggestions if requested
        ai_available = ai_agent.is_available()
        if request.include_ai_suggestions and ai_available:
            # Extract elements for AI processing
            elements = []
            for text_block in analysis.get('text_blocks', []):
                # Handle PDFElement objects
                if hasattr(text_block, 'content'):
                    elements.append({
                        'type': 'text',
                        'content': getattr(text_block, 'content', ''),
                        'page': getattr(text_block, 'page_num', 1)
                    })
                elif isinstance(text_block, dict):
                    elements.append({
                        'type': 'text',
                        'content': text_block.get('content', ''),
                        'page': text_block.get('page_num', 1)
                    })
            
            # Queue AI enhancement in background
            session_id = str(uuid.uuid4())
            background_tasks.add_task(
                enhance_with_ai,
                session_id,
                tag_tree,
                elements
            )
        else:
            session_id = str(uuid.uuid4())
        
        # Helper function to serialize AccessibilityIssue
        def serialize_issue(issue):
            """Convert AccessibilityIssue to dict with proper enum handling"""
            if hasattr(issue, '__dataclass_fields__'):
                from dataclasses import asdict
                issue_dict = asdict(issue)
                # Convert enum values to strings
                if 'severity' in issue_dict and hasattr(issue_dict['severity'], 'value'):
                    issue_dict['severity'] = issue_dict['severity'].value
                if 'wcag_level' in issue_dict and hasattr(issue_dict['wcag_level'], 'value'):
                    issue_dict['wcag_level'] = issue_dict['wcag_level'].value
                return issue_dict
            return issue
        
        # Store session data
        tag_tree_json = tag_tree.to_json()
        serialized_issues = [serialize_issue(issue) for issue in issues]
        
        active_sessions[session_id] = {
            "file_path": file_path,
            "tag_tree": json.loads(tag_tree_json) if isinstance(tag_tree_json, str) else tag_tree_json,
            "issues": serialized_issues,
            "analysis": analysis,
            "metadata": metadata.__dict__,
            "status": "analyzed"
        }
        
        processing_time = time.time() - start_time
        
        # Prepare response
        tag_tree_dict = json.loads(tag_tree_json) if isinstance(tag_tree_json, str) else tag_tree_json
        issues_dict = serialized_issues
        
        return AnalyzeResponse(
            session_id=session_id,
            tag_tree=tag_tree_dict,
            issues=issues_dict,
            metadata=metadata.__dict__,
            ai_available=ai_available,
            processing_time=processing_time
        )
        
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ai/suggest")
async def ai_suggest_roles(request: AISuggestRequest):
    """Use Gemini for role classification suggestions"""
    if request.session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if not ai_agent.is_available():
        raise HTTPException(status_code=503, detail="AI service unavailable")
    
    try:
        # Classify text elements using AI
        suggestions = ai_agent.classify_text_elements(request.elements)
        
        # Update session
        active_sessions[request.session_id]["ai_suggestions"] = suggestions
        
        # Notify via WebSocket
        await notify_websocket(request.session_id, {
            "type": "ai_suggestions",
            "data": suggestions
        })
        
        return {
            "session_id": request.session_id,
            "suggestions": suggestions,
            "model_used": ai_agent.get_model_info().get('ai_mode')
        }
        
    except Exception as e:
        logger.error(f"AI suggestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ai/alt_text")
async def generate_alt_text(request: AIAltTextRequest):
    """Generate alt text for images using Gemini"""
    if request.session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if not ai_agent.is_available():
        raise HTTPException(status_code=503, detail="AI service unavailable")
    
    try:
        import base64
        
        # Decode base64 image
        image_data = base64.b64decode(request.image_data)
        
        # Generate alt text
        alt_text = ai_agent.generate_alt_text(
            image_data,
            context=request.context,
            page_num=request.page_number
        )
        
        return {
            "session_id": request.session_id,
            "alt_text": alt_text,
            "model_used": ai_agent.get_model_info().get('ai_mode')
        }
        
    except Exception as e:
        logger.error(f"Alt text generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/fix")
async def apply_fixes(request: FixRequest):
    """Apply accessibility fixes to PDF"""
    if request.session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = active_sessions[request.session_id]
    
    try:
        # Initialize fix manager
        fix_manager = FixManager(session["file_path"])
        
        # Apply fixes
        applied_fixes = []
        for fix in request.fixes:
            success = fix_manager.apply_fix(
                issue_id=fix.get('issue_id'),
                fix_type=fix.get('type'),
                fix_data=fix.get('data')
            )
            if success:
                applied_fixes.append(fix)
        
        # Create output path
        output_path = Path(session["file_path"]).with_suffix('.accessible.pdf')
        
        # Write fixed PDF
        writer = PDFWriter(
            session["file_path"],
            invisible_fixes=request.apply_invisible
        )
        
        for fix in applied_fixes:
            writer.apply_accessibility_fix(
                fix['type'],
                fix.get('page', 1),
                fix.get('data', {})
            )
        
        writer.save(str(output_path))
        
        # Update session
        session["fixed_pdf_path"] = str(output_path)
        session["applied_fixes"] = applied_fixes
        session["status"] = "fixed"
        
        return {
            "session_id": request.session_id,
            "output_path": str(output_path),
            "applied_fixes": len(applied_fixes),
            "total_requested": len(request.fixes)
        }
        
    except Exception as e:
        logger.error(f"Fix application error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/validate")
async def validate_pdf(request: ValidateRequest):
    """Validate PDF against PDF/UA using veraPDF"""
    if request.session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = active_sessions[request.session_id]
    pdf_path = session.get("fixed_pdf_path", session["file_path"])
    
    try:
        # Run veraPDF validation
        if not verapdf_validator.is_available():
            return {
                "session_id": request.session_id,
                "validation_available": False,
                "message": "veraPDF not installed"
            }
        
        result = verapdf_validator.validate_pdf_ua(pdf_path, profile=request.profile)
        
        if result:
            return {
                "session_id": request.session_id,
                "validation_available": True,
                "compliant": result.compliant,
                "score": result.compliance_score,
                "passed_checks": result.passed_checks,
                "failed_checks": result.failed_checks,
                "total_checks": result.total_checks,
                "errors": result.errors[:10]  # First 10 errors
            }
        else:
            raise HTTPException(status_code=500, detail="Validation failed")
            
    except Exception as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/export/report")
async def export_report(session_id: str, format: str = "html"):
    """Export accessibility report in various formats"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = active_sessions[session_id]
    
    try:
        if format == "html":
            generator = HTMLReportGenerator()
            
            # Prepare report data
            report_data = {
                "document_info": session.get("metadata", {}),
                "issues": session.get("issues", []),
                "applied_fixes": session.get("applied_fixes", []),
                "validation_result": session.get("validation_result"),
                "ai_cost": ai_agent.get_cost_summary() if ai_agent.is_available() else None
            }
            
            # Generate HTML report
            html_content = generator.generate_report(
                pdf_path=session["file_path"],
                **report_data
            )
            
            # Save report
            report_path = Path(session["file_path"]).with_suffix('.report.html')
            report_path.write_text(html_content)
            
            return FileResponse(
                report_path,
                media_type="text/html",
                filename=f"{Path(session['file_path']).stem}_report.html"
            )
            
        elif format == "json":
            # Export as JSON
            report_data = {
                "session_id": session_id,
                "metadata": session.get("metadata"),
                "tag_tree": session.get("tag_tree"),
                "issues": session.get("issues"),
                "fixes": session.get("applied_fixes"),
                "validation": session.get("validation_result")
            }
            
            return JSONResponse(content=report_data)
            
        else:
            raise HTTPException(status_code=400, detail="Unsupported format")
            
    except Exception as e:
        logger.error(f"Report export error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket for real-time updates"""
    await websocket.accept()
    websocket_connections[session_id] = websocket
    
    try:
        while True:
            # Keep connection alive and handle messages
            data = await websocket.receive_text()
            
            # Echo back or handle commands
            await websocket.send_json({
                "type": "echo",
                "data": data,
                "timestamp": datetime.now().isoformat()
            })
            
    except Exception as e:
        logger.info(f"WebSocket disconnected: {e}")
    finally:
        if session_id in websocket_connections:
            del websocket_connections[session_id]

@app.get("/api/session/{session_id}/status")
async def get_session_status(session_id: str):
    """Get current session status"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = active_sessions[session_id]
    return {
        "session_id": session_id,
        "status": session.get("status"),
        "filename": session.get("filename"),
        "created_at": session.get("created_at"),
        "has_fixes": "applied_fixes" in session,
        "has_validation": "validation_result" in session
    }

@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    """Clean up session and temporary files"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = active_sessions[session_id]
    
    # Clean up files
    for key in ["file_path", "fixed_pdf_path"]:
        if key in session:
            try:
                Path(session[key]).unlink()
            except:
                pass
    
    # Remove session
    del active_sessions[session_id]
    
    return {"message": "Session deleted successfully"}

# Background tasks
async def enhance_with_ai(session_id: str, tag_tree: AccessibilityTagTree, elements: List[Dict]):
    """Background task to enhance content with AI"""
    try:
        # Notify start
        await notify_websocket(session_id, {
            "type": "ai_processing",
            "status": "started"
        })
        
        # Process elements with AI
        enhanced_elements = ai_agent.classify_text_elements(elements)
        
        # Update tag tree with AI suggestions
        for elem in enhanced_elements:
            if elem.get('ai_suggestion'):
                tag_tree.update_node_status(
                    node_id=elem.get('id'),
                    status='ai-suggested'
                )
        
        # Store results
        if session_id in active_sessions:
            active_sessions[session_id]["ai_enhanced"] = True
            active_sessions[session_id]["enhanced_elements"] = enhanced_elements
        
        # Notify completion
        await notify_websocket(session_id, {
            "type": "ai_processing",
            "status": "completed",
            "enhanced_count": len(enhanced_elements)
        })
        
    except Exception as e:
        logger.error(f"AI enhancement error: {e}")
        await notify_websocket(session_id, {
            "type": "ai_processing",
            "status": "error",
            "error": str(e)
        })

# Authentication endpoints
@app.post("/api/auth/register")
async def register(name: str, email: str):
    """Register for API access (demo mode)"""
    api_key_info = create_api_key(name, email, tier="free")
    return {
        "api_key": api_key_info.api_key,
        "message": "API key created. Include in X-API-Key header for requests.",
        "tier": api_key_info.tier,
        "limits": {
            "daily_pdfs": 10,
            "max_pdf_size_mb": 10,
            "ai_calls": 100
        }
    }

@app.post("/api/auth/token")
async def get_token(api_key: str = Depends(get_api_key)):
    """Exchange API key for JWT token"""
    from datetime import timedelta
    
    # Get user info from API key
    user_info = api_keys_db.get(api_key, {})
    
    # Create token
    access_token = create_access_token(
        data={"sub": api_key, "tier": user_info.get("tier", "free")},
        expires_delta=timedelta(minutes=60)
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=3600
    )

@app.get("/api/usage")
async def get_usage(api_key: str = Depends(get_api_key)):
    """Get API usage statistics"""
    return {
        "api_key": api_key[:12] + "...",
        "usage": usage_tracker.get_usage(api_key),
        "tier": api_keys_db.get(api_key, {}).get("tier", "free")
    }

@app.get("/api/download/{session_id}")
async def download_pdf(session_id: str, api_key: Optional[str] = None):
    """Download the original or processed PDF file for a session"""
    # Validate API key
    if not api_key or api_key not in api_keys_db:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session_data = active_sessions[session_id]
    file_path = session_data.get("file_path")

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="PDF file not found")

    # Get original filename for proper Content-Disposition header
    filename = session_data.get("filename", f"{session_id}.pdf")

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=filename
    )

# Health check
@app.get("/health")
async def health_check():
    """API health check"""
    return {
        "status": "healthy",
        "ai_available": ai_agent.is_available(),
        "verapdf_available": verapdf_validator.is_available(),
        "active_sessions": len(active_sessions),
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    # Run the API server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )