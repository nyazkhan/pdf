import json
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
import logging
from .accessibility_rules import AccessibilityIssue, Severity, WCAGLevel
from .html_report_generator import HTMLReportGenerator
from .verapdf_validator import VeraPDFValidationResult

logger = logging.getLogger(__name__)


class ReportManager:
    def __init__(self, db_path: str = "accessibility_reports.db"):
        self.db_path = db_path
        self.html_generator = HTMLReportGenerator()
        self._init_database()
    
    def _sanitize_for_json(self, data):
        """Remove non-serializable data from metadata"""
        if isinstance(data, dict):
            return {k: self._sanitize_for_json(v) for k, v in data.items() 
                    if not isinstance(v, bytes)}
        elif isinstance(data, (list, tuple)):
            return [self._sanitize_for_json(item) for item in data 
                    if not isinstance(item, bytes)]
        elif isinstance(data, bytes):
            return None  # Skip bytes data
        else:
            return data
    
    def _init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pdf_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE,
                file_hash TEXT,
                analyzed_date TIMESTAMP,
                total_issues INTEGER,
                compliance_score REAL,
                metadata TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accessibility_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER,
                issue_id TEXT,
                title TEXT,
                description TEXT,
                severity TEXT,
                wcag_criteria TEXT,
                wcag_level TEXT,
                page_num INTEGER,
                bbox_x0 REAL,
                bbox_y0 REAL,
                bbox_x1 REAL,
                bbox_y1 REAL,
                element_type TEXT,
                current_value TEXT,
                suggested_fix TEXT,
                auto_fixable BOOLEAN,
                status TEXT DEFAULT 'pending',
                applied_fix TEXT,
                metadata TEXT,
                FOREIGN KEY (document_id) REFERENCES pdf_documents(id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def save_report(self, file_path: str, issues: List[AccessibilityIssue], 
                   document_metadata: Dict, file_hash: str = None) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Calculate summary statistics
            total_issues = len(issues)
            compliance_score = self._calculate_compliance_score(issues)
            
            # Insert or update document record
            cursor.execute("""
                INSERT OR REPLACE INTO pdf_documents 
                (file_path, file_hash, analyzed_date, total_issues, compliance_score, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                file_path,
                file_hash or "",
                datetime.now().isoformat(),
                total_issues,
                compliance_score,
                json.dumps(self._sanitize_for_json(document_metadata))
            ))
            
            document_id = cursor.lastrowid
            
            # Delete existing issues for this document
            cursor.execute("DELETE FROM accessibility_issues WHERE document_id = ?", (document_id,))
            
            # Insert new issues
            for issue in issues:
                cursor.execute("""
                    INSERT INTO accessibility_issues 
                    (document_id, issue_id, title, description, severity, wcag_criteria, wcag_level,
                     page_num, bbox_x0, bbox_y0, bbox_x1, bbox_y1, element_type, current_value,
                     suggested_fix, auto_fixable, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    document_id,
                    issue.issue_id,
                    issue.title,
                    issue.description,
                    issue.severity.value,
                    issue.wcag_criteria,
                    issue.wcag_level.value,
                    issue.page_num,
                    issue.bbox[0],
                    issue.bbox[1],
                    issue.bbox[2],
                    issue.bbox[3],
                    issue.element_type,
                    issue.current_value,
                    issue.suggested_fix,
                    issue.auto_fixable,
                    json.dumps(self._sanitize_for_json(issue.metadata))
                ))
            
            conn.commit()
            logger.info(f"Saved report for {file_path} with {total_issues} issues")
            return document_id
            
        except Exception as e:
            logger.error(f"Failed to save report: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def load_report(self, file_path: str) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Get document info
            cursor.execute("""
                SELECT * FROM pdf_documents WHERE file_path = ?
            """, (file_path,))
            
            doc_row = cursor.fetchone()
            if not doc_row:
                return None
            
            doc_columns = [desc[0] for desc in cursor.description]
            document = dict(zip(doc_columns, doc_row))
            
            # Get issues
            cursor.execute("""
                SELECT * FROM accessibility_issues WHERE document_id = ?
            """, (document["id"],))
            
            issue_rows = cursor.fetchall()
            issue_columns = [desc[0] for desc in cursor.description]
            
            issues = []
            for row in issue_rows:
                issue_dict = dict(zip(issue_columns, row))
                
                # Convert back to AccessibilityIssue object
                issue = AccessibilityIssue(
                    issue_id=issue_dict["issue_id"],
                    title=issue_dict["title"],
                    description=issue_dict["description"],
                    severity=Severity(issue_dict["severity"]),
                    wcag_criteria=issue_dict["wcag_criteria"],
                    wcag_level=WCAGLevel(issue_dict["wcag_level"]),
                    page_num=issue_dict["page_num"],
                    bbox=(issue_dict["bbox_x0"], issue_dict["bbox_y0"],
                          issue_dict["bbox_x1"], issue_dict["bbox_y1"]),
                    element_type=issue_dict["element_type"],
                    current_value=issue_dict["current_value"] or "",
                    suggested_fix=issue_dict["suggested_fix"] or "",
                    auto_fixable=bool(issue_dict["auto_fixable"]),
                    metadata=json.loads(issue_dict["metadata"] or "{}")
                )
                issues.append(issue)
            
            return {
                "document": document,
                "issues": issues,
                "metadata": json.loads(document["metadata"] or "{}")
            }
            
        except Exception as e:
            logger.error(f"Failed to load report: {e}")
            return None
        finally:
            conn.close()
    
    def update_issue_status(self, issue_id: str, status: str, applied_fix: str = None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE accessibility_issues 
                SET status = ?, applied_fix = ?
                WHERE issue_id = ?
            """, (status, applied_fix, issue_id))
            
            conn.commit()
            
        except Exception as e:
            logger.error(f"Failed to update issue status: {e}")
        finally:
            conn.close()
    
    def export_json_report(self, file_path: str, output_path: str = None) -> str:
        report_data = self.load_report(file_path)
        
        if not report_data:
            raise ValueError(f"No report found for {file_path}")
        
        # Convert issues to serializable format
        issues_data = []
        for issue in report_data["issues"]:
            issues_data.append({
                "issue_id": issue.issue_id,
                "title": issue.title,
                "description": issue.description,
                "severity": issue.severity.value,
                "wcag_criteria": issue.wcag_criteria,
                "wcag_level": issue.wcag_level.value,
                "page_num": issue.page_num,
                "bbox": issue.bbox,
                "element_type": issue.element_type,
                "current_value": issue.current_value,
                "suggested_fix": issue.suggested_fix,
                "auto_fixable": issue.auto_fixable,
                "metadata": issue.metadata
            })
        
        export_data = {
            "document_path": file_path,
            "analysis_date": report_data["document"]["analyzed_date"],
            "total_issues": report_data["document"]["total_issues"],
            "compliance_score": report_data["document"]["compliance_score"],
            "summary": self._generate_summary_stats(report_data["issues"]),
            "issues": issues_data,
            "document_metadata": report_data["metadata"]
        }
        
        if not output_path:
            output_path = f"{Path(file_path).stem}_accessibility_report.json"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Exported report to {output_path}")
        return output_path
    
    def _calculate_compliance_score(self, issues: List[AccessibilityIssue]) -> float:
        if not issues:
            return 100.0
        
        total_deductions = 0
        for issue in issues:
            if issue.severity == Severity.CRITICAL:
                total_deductions += 10
            elif issue.severity == Severity.WARNING:
                total_deductions += 5
            else:  # INFO
                total_deductions += 1
        
        score = max(0, 100 - total_deductions)
        return round(score, 1)
    
    def _generate_summary_stats(self, issues: List[AccessibilityIssue]) -> Dict:
        if not issues:
            return {
                "critical_issues": 0,
                "warning_issues": 0,
                "info_issues": 0,
                "auto_fixable_issues": 0,
                "issues_by_page": {},
                "issues_by_type": {}
            }
        
        critical = sum(1 for i in issues if i.severity == Severity.CRITICAL)
        warning = sum(1 for i in issues if i.severity == Severity.WARNING)
        info = sum(1 for i in issues if i.severity == Severity.INFO)
        auto_fixable = sum(1 for i in issues if i.auto_fixable)
        
        # Group by page
        issues_by_page = {}
        for issue in issues:
            page = issue.page_num
            if page not in issues_by_page:
                issues_by_page[page] = 0
            issues_by_page[page] += 1
        
        # Group by type
        issues_by_type = {}
        for issue in issues:
            issue_type = issue.element_type
            if issue_type not in issues_by_type:
                issues_by_type[issue_type] = 0
            issues_by_type[issue_type] += 1
        
        return {
            "critical_issues": critical,
            "warning_issues": warning,
            "info_issues": info,
            "auto_fixable_issues": auto_fixable,
            "issues_by_page": issues_by_page,
            "issues_by_type": issues_by_type
        }
    
    def get_recent_reports(self, limit: int = 10) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT file_path, analyzed_date, total_issues, compliance_score
                FROM pdf_documents
                ORDER BY analyzed_date DESC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
            return [dict(zip(columns, row)) for row in rows]
            
        finally:
            conn.close()
    
    def export_html_report(self, file_path: str, output_path: str = None,
                          verapdf_result: Optional[VeraPDFValidationResult] = None,
                          ai_cost_summary: Optional[Dict] = None) -> str:
        """Export comprehensive HTML accessibility report"""
        report_data = self.load_report(file_path)
        
        if not report_data:
            raise ValueError(f"No report found for {file_path}")
        
        # Generate HTML report
        html_path = self.html_generator.generate_report(
            file_path=file_path,
            issues=report_data["issues"],
            document_metadata=report_data["metadata"],
            summary_stats=self._generate_summary_stats(report_data["issues"]),
            verapdf_result=verapdf_result,
            ai_cost_summary=ai_cost_summary,
            output_path=output_path
        )
        
        logger.info(f"Generated HTML report: {html_path}")
        return html_path
    
    def generate_comprehensive_report(self, file_path: str, issues: List[AccessibilityIssue],
                                    document_metadata: Dict, file_hash: str = None,
                                    verapdf_result: Optional[VeraPDFValidationResult] = None,
                                    ai_cost_summary: Optional[Dict] = None,
                                    export_formats: List[str] = ["json", "html"]) -> Dict[str, str]:
        """Generate comprehensive reports in multiple formats"""
        
        # Save to database first
        document_id = self.save_report(file_path, issues, document_metadata, file_hash)
        
        export_paths = {}
        
        # Export JSON if requested
        if "json" in export_formats:
            json_path = self.export_json_report(file_path)
            export_paths["json"] = json_path
        
        # Export HTML if requested
        if "html" in export_formats:
            html_path = self.export_html_report(
                file_path=file_path,
                verapdf_result=verapdf_result,
                ai_cost_summary=ai_cost_summary
            )
            export_paths["html"] = html_path
        
        # Export additional formats if requested
        if "pdf" in export_formats:
            # Could add PDF report generation here
            pass
        
        logger.info(f"Generated comprehensive reports: {list(export_paths.keys())}")
        return export_paths