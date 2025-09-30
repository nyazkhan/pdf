import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum

from .accessibility_rules import AccessibilityIssue

logger = logging.getLogger(__name__)


class FixType(Enum):
    ALT_TEXT = "alt_text"
    HEADING_LEVEL = "heading_level"
    TABLE_SUMMARY = "table_summary"
    METADATA = "metadata"
    READING_ORDER = "reading_order"


class FixStatus(Enum):
    PENDING = "pending"
    APPLIED = "applied"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class Fix:
    issue_id: str
    fix_type: FixType
    original_value: str
    fixed_value: str
    ai_generated: bool = False
    user_modified: bool = False
    status: FixStatus = FixStatus.PENDING
    timestamp: str = None
    confidence: float = 1.0
    notes: str = ""
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()


class FixManager:
    def __init__(self):
        self.fixes: Dict[str, Fix] = {}
        self.history: List[Dict[str, Any]] = []
        self.session_file: Optional[str] = None
        self.pdf_path: Optional[str] = None
        self.session_name: Optional[str] = None
        self._max_history = 50  # Limit undo history
        
    def set_pdf(self, pdf_path: str):
        """Set the current PDF being worked on"""
        self.pdf_path = pdf_path
        self.session_name = Path(pdf_path).stem
        
    def add_fix(self, issue: AccessibilityIssue, fix_type: FixType, 
                fixed_value: str, ai_generated: bool = False) -> bool:
        """Add a fix for an accessibility issue"""
        try:
            # Create fix record
            fix = Fix(
                issue_id=issue.issue_id,
                fix_type=fix_type,
                original_value=issue.current_value,
                fixed_value=fixed_value,
                ai_generated=ai_generated,
                user_modified=not ai_generated
            )
            
            # Add to history for undo
            self._add_to_history("add_fix", {
                "issue_id": issue.issue_id,
                "fix": asdict(fix)
            })
            
            # Store fix
            self.fixes[issue.issue_id] = fix
            
            logger.info(f"Added fix for issue {issue.issue_id}: {fix_type.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add fix: {e}")
            return False
    
    def update_fix(self, issue_id: str, fixed_value: str, user_modified: bool = True) -> bool:
        """Update an existing fix"""
        if issue_id not in self.fixes:
            logger.warning(f"No fix found for issue {issue_id}")
            return False
        
        try:
            fix = self.fixes[issue_id]
            
            # Add to history
            self._add_to_history("update_fix", {
                "issue_id": issue_id,
                "old_value": fix.fixed_value,
                "new_value": fixed_value
            })
            
            # Update fix
            fix.fixed_value = fixed_value
            fix.user_modified = user_modified
            fix.timestamp = datetime.now().isoformat()
            
            logger.info(f"Updated fix for issue {issue_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update fix: {e}")
            return False
    
    def remove_fix(self, issue_id: str) -> bool:
        """Remove a fix"""
        if issue_id not in self.fixes:
            return False
        
        try:
            # Add to history
            self._add_to_history("remove_fix", {
                "issue_id": issue_id,
                "fix": asdict(self.fixes[issue_id])
            })
            
            # Remove fix
            del self.fixes[issue_id]
            
            logger.info(f"Removed fix for issue {issue_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove fix: {e}")
            return False
    
    def mark_fix_applied(self, issue_id: str) -> bool:
        """Mark a fix as successfully applied"""
        if issue_id not in self.fixes:
            return False
        
        self.fixes[issue_id].status = FixStatus.APPLIED
        self.fixes[issue_id].timestamp = datetime.now().isoformat()
        return True
    
    def mark_fix_failed(self, issue_id: str, error_msg: str = "") -> bool:
        """Mark a fix as failed to apply"""
        if issue_id not in self.fixes:
            return False
        
        self.fixes[issue_id].status = FixStatus.FAILED
        self.fixes[issue_id].notes = error_msg
        self.fixes[issue_id].timestamp = datetime.now().isoformat()
        return True
    
    def get_fix(self, issue_id: str) -> Optional[Fix]:
        """Get a specific fix"""
        return self.fixes.get(issue_id)
    
    def get_fixes_by_type(self, fix_type: FixType) -> List[Fix]:
        """Get all fixes of a specific type"""
        return [fix for fix in self.fixes.values() if fix.fix_type == fix_type]
    
    def get_fixes_by_status(self, status: FixStatus) -> List[Fix]:
        """Get all fixes with a specific status"""
        return [fix for fix in self.fixes.values() if fix.status == status]
    
    def get_pending_fixes(self) -> List[Fix]:
        """Get all pending fixes"""
        return self.get_fixes_by_status(FixStatus.PENDING)
    
    def get_applied_fixes(self) -> List[Fix]:
        """Get all applied fixes"""
        return self.get_fixes_by_status(FixStatus.APPLIED)
    
    def get_ai_generated_fixes(self) -> List[Fix]:
        """Get all AI-generated fixes"""
        return [fix for fix in self.fixes.values() if fix.ai_generated]
    
    def get_fix_summary(self) -> Dict[str, Any]:
        """Get summary statistics about fixes"""
        total_fixes = len(self.fixes)
        applied_fixes = len(self.get_applied_fixes())
        pending_fixes = len(self.get_pending_fixes())
        ai_fixes = len(self.get_ai_generated_fixes())
        failed_fixes = len(self.get_fixes_by_status(FixStatus.FAILED))
        
        fixes_by_type = {}
        for fix_type in FixType:
            fixes_by_type[fix_type.value] = len(self.get_fixes_by_type(fix_type))
        
        return {
            "total_fixes": total_fixes,
            "applied_fixes": applied_fixes,
            "pending_fixes": pending_fixes,
            "failed_fixes": failed_fixes,
            "ai_generated_fixes": ai_fixes,
            "user_modified_fixes": total_fixes - ai_fixes,
            "fixes_by_type": fixes_by_type,
            "completion_percentage": round((applied_fixes / max(total_fixes, 1)) * 100, 1)
        }
    
    def save_session(self, session_path: str = None) -> bool:
        """Save current fixing session"""
        try:
            if not session_path:
                if not self.session_name:
                    session_path = "accessibility_session.json"
                else:
                    session_path = f"{self.session_name}_session.json"
            
            # Prepare fixes data with proper serialization
            fixes_data = {}
            for issue_id, fix in self.fixes.items():
                fix_dict = asdict(fix)
                # Convert enums to strings for JSON serialization
                fix_dict['fix_type'] = fix.fix_type.value
                fix_dict['status'] = fix.status.value
                fixes_data[issue_id] = fix_dict
            
            session_data = {
                "pdf_path": self.pdf_path,
                "session_name": self.session_name,
                "created_date": datetime.now().isoformat(),
                "fixes": fixes_data,
                "summary": self.get_fix_summary(),
                "version": "1.0"
            }
            
            with open(session_path, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
            
            self.session_file = session_path
            logger.info(f"Saved session to {session_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
            return False
    
    def load_session(self, session_path: str) -> bool:
        """Load a fixing session"""
        try:
            if not Path(session_path).exists():
                logger.error(f"Session file not found: {session_path}")
                return False
            
            with open(session_path, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            # Validate session data
            if "fixes" not in session_data:
                logger.error("Invalid session file format")
                return False
            
            # Clear current state
            self.fixes.clear()
            self.history.clear()
            
            # Load session data
            self.pdf_path = session_data.get("pdf_path")
            self.session_name = session_data.get("session_name")
            self.session_file = session_path
            
            # Load fixes
            for issue_id, fix_data in session_data["fixes"].items():
                fix = Fix(
                    issue_id=fix_data["issue_id"],
                    fix_type=FixType(fix_data["fix_type"]),
                    original_value=fix_data["original_value"],
                    fixed_value=fix_data["fixed_value"],
                    ai_generated=fix_data.get("ai_generated", False),
                    user_modified=fix_data.get("user_modified", True),
                    status=FixStatus(fix_data.get("status", "pending")),
                    timestamp=fix_data.get("timestamp"),
                    confidence=fix_data.get("confidence", 1.0),
                    notes=fix_data.get("notes", "")
                )
                self.fixes[issue_id] = fix
            
            logger.info(f"Loaded session from {session_path} with {len(self.fixes)} fixes")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load session: {e}")
            return False
    
    def export_fixes_for_pdf(self) -> Dict[str, Any]:
        """Export fixes in format suitable for PDF writer"""
        export_data = {
            "pdf_path": self.pdf_path,
            "export_date": datetime.now().isoformat(),
            "fixes": [],
            "summary": self.get_fix_summary()
        }
        
        for fix in self.fixes.values():
            if fix.status != FixStatus.SKIPPED:
                export_data["fixes"].append({
                    "issue_id": fix.issue_id,
                    "type": fix.fix_type.value,
                    "value": fix.fixed_value,
                    "status": fix.status.value,
                    "ai_generated": fix.ai_generated
                })
        
        return export_data
    
    def undo(self) -> bool:
        """Undo the last action"""
        if not self.history:
            return False
        
        try:
            last_action = self.history.pop()
            action_type = last_action["action"]
            data = last_action["data"]
            
            if action_type == "add_fix":
                # Remove the added fix
                issue_id = data["issue_id"]
                if issue_id in self.fixes:
                    del self.fixes[issue_id]
                    
            elif action_type == "update_fix":
                # Revert to old value
                issue_id = data["issue_id"]
                if issue_id in self.fixes:
                    self.fixes[issue_id].fixed_value = data["old_value"]
                    
            elif action_type == "remove_fix":
                # Re-add the removed fix
                issue_id = data["issue_id"]
                fix_data = data["fix"]
                fix = Fix(**fix_data)
                self.fixes[issue_id] = fix
            
            logger.info(f"Undid action: {action_type}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to undo: {e}")
            return False
    
    def clear_fixes(self):
        """Clear all fixes and history"""
        self.fixes.clear()
        self.history.clear()
        logger.info("Cleared all fixes and history")
    
    def _add_to_history(self, action: str, data: Dict[str, Any]):
        """Add action to history for undo"""
        self.history.append({
            "action": action,
            "data": data,
            "timestamp": datetime.now().isoformat()
        })
        
        # Limit history size
        if len(self.history) > self._max_history:
            self.history.pop(0)
    
    def has_unsaved_changes(self) -> bool:
        """Check if there are unsaved changes"""
        if not self.fixes:
            return False
        
        # If we have fixes but no session file, we have unsaved changes
        if not self.session_file:
            return True
        
        # Check if session file exists and is newer than fixes
        try:
            if not Path(self.session_file).exists():
                return True
            
            # Simple check - if any fix has been modified since last save
            session_mtime = Path(self.session_file).stat().st_mtime
            for fix in self.fixes.values():
                fix_time = datetime.fromisoformat(fix.timestamp).timestamp()
                if fix_time > session_mtime:
                    return True
            
            return False
            
        except Exception:
            return True  # Assume unsaved if we can't check