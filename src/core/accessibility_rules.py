from enum import Enum
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import re
import logging
from .pdf_parser import PDFElement, PDFImage
from .pdf_techniques import PDFTechnique, get_technique_by_code, get_remediation_guidance
from .verapdf_validator import VeraPDFValidator, VeraPDFValidationResult

logger = logging.getLogger(__name__)


class Severity(Enum):
    CRITICAL = "critical"
    WARNING = "warning" 
    INFO = "info"


class WCAGLevel(Enum):
    A = "A"
    AA = "AA"
    AAA = "AAA"


@dataclass
class AccessibilityIssue:
    issue_id: str
    title: str
    description: str
    severity: Severity
    wcag_criteria: str
    wcag_level: WCAGLevel
    page_num: int
    bbox: Tuple[float, float, float, float]
    element_type: str
    current_value: str = ""
    suggested_fix: str = ""
    auto_fixable: bool = False
    metadata: Dict = None
    pdf_technique: str = ""  # Reference to PDF1-PDF23
    remediation_guidance: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.remediation_guidance is None:
            self.remediation_guidance = {}


class WCAGValidator:
    def __init__(self, wcag_level: str = "AA", enable_verapdf: bool = True):
        self.wcag_level = WCAGLevel(wcag_level)
        self.issues: List[AccessibilityIssue] = []
        
        # Initialize veraPDF validator
        self.verapdf_validator = None
        if enable_verapdf:
            self.verapdf_validator = VeraPDFValidator()
            if not self.verapdf_validator.is_available():
                logger.warning("veraPDF not available - final PDF/UA validation will be skipped")
        
    def validate_document(self, analysis: Dict) -> List[AccessibilityIssue]:
        self.issues = []
        
        # Run all validation rules (existing)
        self._check_images_alt_text(analysis.get("images", []))
        self._check_heading_structure(analysis.get("headings", []))
        self._check_empty_pages(analysis)
        self._check_reading_order(analysis.get("reading_order", []))
        self._check_tables(analysis.get("tables", []))
        self._check_document_metadata(analysis.get("metadata", {}))
        
        # New PDF technique validations
        self._check_pdf2_bookmarks(analysis)
        self._check_pdf3_reading_order_enhanced(analysis)
        self._check_pdf4_decorative_images(analysis.get("images", []))
        self._check_pdf6_table_structure_enhanced(analysis.get("tables", []))
        self._check_pdf7_scanned_content(analysis.get("scanned_pages", []))
        self._check_pdf10_form_labels(analysis.get("form_fields", []))
        self._check_pdf11_link_structure(analysis.get("links", []))
        self._check_pdf12_form_name_role_value(analysis.get("form_fields", []))
        self._check_pdf16_document_language(analysis)
        self._check_pdf18_document_title(analysis.get("metadata", {}))
        self._check_pdf21_list_structure(analysis.get("lists", []))
        
        logger.info(f"Found {len(self.issues)} accessibility issues")
        return self.issues
    
    def _check_images_alt_text(self, images: List[PDFImage]):
        """PDF1 & PDF4: Check images for alt text and decorative marking"""
        technique_pdf1 = get_technique_by_code("PDF1")
        technique_pdf4 = get_technique_by_code("PDF4")
        
        for i, image in enumerate(images):
            # Skip if image is properly marked as decorative (artifact)
            if image.is_decorative:
                logger.debug(f"Image {image.image_id} on page {image.page_num} is marked as decorative")
                continue
            
            # Check if image has alt text in any acceptable location
            has_proper_alt = (
                image.has_alt_in_xobject or 
                image.has_alt_in_structure or 
                (image.alt_text and image.alt_text.strip())
            )
            
            if not has_proper_alt:
                # Missing alt text completely - CRITICAL issue
                issue = AccessibilityIssue(
                    issue_id=f"pdf1_img_alt_{image.page_num}_{image.image_id}",
                    title="Image Missing Alt Text (/Alt Entry)",
                    description="Image does not have alternative text in XObject, structure tree, or marked content",
                    severity=Severity.CRITICAL,
                    wcag_criteria=technique_pdf1.wcag_criteria,
                    wcag_level=WCAGLevel.A,
                    page_num=image.page_num,
                    bbox=image.bbox,
                    element_type="image",
                    current_value="No alt text found",
                    suggested_fix="Add descriptive alt text using /Alt entry in image properties or mark as artifact if decorative",
                    auto_fixable=True,
                    pdf_technique="PDF1",
                    remediation_guidance=get_remediation_guidance("PDF1"),
                    metadata={
                        "image_id": image.image_id,
                        "image_width": image.pil_image.width if image.pil_image else 0,
                        "image_height": image.pil_image.height if image.pil_image else 0,
                        "image_format": image.pil_image.format if image.pil_image else "unknown",
                        "has_alt_in_xobject": image.has_alt_in_xobject,
                        "has_alt_in_structure": image.has_alt_in_structure,
                        "is_decorative": image.is_decorative
                    }
                )
                self.issues.append(issue)
            
            elif image.alt_text and not image.alt_text.strip():
                # Has alt text but it's empty - WARNING issue
                issue = AccessibilityIssue(
                    issue_id=f"pdf1_img_empty_alt_{image.page_num}_{image.image_id}",
                    title="Image Has Empty Alt Text",
                    description="Image has alt text attribute but the value is empty",
                    severity=Severity.WARNING,
                    wcag_criteria=technique_pdf1.wcag_criteria,
                    wcag_level=WCAGLevel.A,
                    page_num=image.page_num,
                    bbox=image.bbox,
                    element_type="image",
                    current_value="Empty alt text",
                    suggested_fix="Provide meaningful alt text or mark as artifact if decorative",
                    auto_fixable=True,
                    pdf_technique="PDF1",
                    remediation_guidance=get_remediation_guidance("PDF1"),
                    metadata={
                        "image_id": image.image_id,
                        "has_alt_in_xobject": image.has_alt_in_xobject,
                        "has_alt_in_structure": image.has_alt_in_structure
                    }
                )
                self.issues.append(issue)
    
    def _check_heading_structure(self, headings: List[PDFElement]):
        """PDF9: Check headings are marked with proper heading tags"""
        technique = get_technique_by_code("PDF9")
        
        if not headings:
            return
            
        # Sort headings by page and position
        sorted_headings = sorted(headings, key=lambda h: (h.page_num, -h.bbox[1], h.bbox[0]))
        
        prev_level = 0
        for heading in sorted_headings:
            current_level = heading.metadata.get("heading_level", 6)
            
            # Check for skipped levels
            if current_level - prev_level > 1:
                issue = AccessibilityIssue(
                    issue_id=f"pdf9_heading_skip_{heading.page_num}_{current_level}",
                    title="Heading Level Hierarchy Skipped",
                    description=f"Heading structure jumps from H{prev_level} to H{current_level}, violating hierarchy",
                    severity=Severity.WARNING,
                    wcag_criteria=technique.wcag_criteria,
                    wcag_level=WCAGLevel.A,
                    page_num=heading.page_num,
                    bbox=heading.bbox,
                    element_type="heading",
                    current_value=f"H{current_level}: {heading.content[:50]}...",
                    suggested_fix=f"Change to H{prev_level + 1} or add intermediate heading levels",
                    auto_fixable=False,
                    pdf_technique="PDF9",
                    remediation_guidance=get_remediation_guidance("PDF9"),
                    metadata={"current_level": current_level, "suggested_level": prev_level + 1}
                )
                self.issues.append(issue)
            
            prev_level = current_level
        
        # Check for missing H1
        h1_found = any(h.metadata.get("heading_level") == 1 for h in headings)
        if not h1_found:
            issue = AccessibilityIssue(
                issue_id="pdf9_missing_h1",
                title="Missing Main Heading (H1)",
                description="Document structure lacks a main heading marked with H1 element",
                severity=Severity.WARNING,
                wcag_criteria=technique.wcag_criteria,
                wcag_level=WCAGLevel.A,
                page_num=1,
                bbox=(0, 0, 100, 50),
                element_type="document",
                current_value="No H1 heading element found",
                suggested_fix="Add a main heading using H1 structure element",
                auto_fixable=False,
                pdf_technique="PDF9",
                remediation_guidance=get_remediation_guidance("PDF9")
            )
            self.issues.append(issue)
    
    def _check_empty_pages(self, analysis: Dict):
        text_blocks = analysis.get("text_blocks", [])
        images = analysis.get("images", [])
        total_pages = analysis.get("total_pages", 0)
        
        # Group content by page
        pages_with_content = set()
        for block in text_blocks:
            if block.content.strip():
                pages_with_content.add(block.page_num)
        
        for image in images:
            pages_with_content.add(image.page_num)
        
        # Check for empty pages
        for page_num in range(total_pages):
            if page_num not in pages_with_content:
                issue = AccessibilityIssue(
                    issue_id=f"empty_page_{page_num}",
                    title="Empty Page",
                    description="Page appears to be empty or contains no accessible content",
                    severity=Severity.INFO,
                    wcag_criteria="2.4.1 Bypass Blocks",
                    wcag_level=WCAGLevel.A,
                    page_num=page_num,
                    bbox=(0, 0, 595, 842),  # Standard A4 size
                    element_type="page",
                    current_value="Empty page",
                    suggested_fix="Remove empty page or add content",
                    auto_fixable=False
                )
                self.issues.append(issue)
    
    def _check_reading_order(self, reading_order: List[PDFElement]):
        if len(reading_order) < 2:
            return
        
        # Check for potential reading order issues
        for i in range(len(reading_order) - 1):
            current = reading_order[i]
            next_elem = reading_order[i + 1]
            
            # Check if elements are on the same page but vertically misaligned
            if (current.page_num == next_elem.page_num and
                abs(current.bbox[1] - next_elem.bbox[1]) > 50 and  # Y difference > 50 points
                current.bbox[0] > next_elem.bbox[0]):  # Current is to the right of next
                
                issue = AccessibilityIssue(
                    issue_id=f"reading_order_{current.page_num}_{i}",
                    title="Potential Reading Order Issue",
                    description="Elements may not be in logical reading order",
                    severity=Severity.WARNING,
                    wcag_criteria="1.3.2 Meaningful Sequence",
                    wcag_level=WCAGLevel.A,
                    page_num=current.page_num,
                    bbox=current.bbox,
                    element_type=current.type,
                    current_value=f"Element appears before: {next_elem.content[:30]}...",
                    suggested_fix="Review and adjust reading order",
                    auto_fixable=False
                )
                self.issues.append(issue)
    
    def _check_tables(self, tables: List[PDFElement]):
        for table in tables:
            table_data = table.metadata.get("data", [])
            
            if not table_data:
                continue
            
            # Check for table headers
            first_row = table_data[0] if table_data else []
            has_headers = self._detect_table_headers(table_data)
            
            if not has_headers:
                issue = AccessibilityIssue(
                    issue_id=f"table_headers_{table.page_num}_{table.metadata.get('table_id', 0)}",
                    title="Table Missing Headers",
                    description="Table does not appear to have proper headers",
                    severity=Severity.WARNING,
                    wcag_criteria="1.3.1 Info and Relationships",
                    wcag_level=WCAGLevel.A,
                    page_num=table.page_num,
                    bbox=table.bbox,
                    element_type="table",
                    current_value=f"Table with {len(table_data)} rows",
                    suggested_fix="Add header row to table or mark existing headers",
                    auto_fixable=False,
                    metadata={"table_data": table_data}
                )
                self.issues.append(issue)
    
    def _detect_table_headers(self, table_data: List[List[str]]) -> bool:
        if not table_data or len(table_data) < 2:
            return False
        
        first_row = table_data[0]
        
        # Simple heuristics for header detection
        header_indicators = 0
        
        for cell in first_row:
            if cell:
                cell_text = str(cell).strip()
                # Check if cell looks like a header
                if (cell_text.isupper() or  # All caps
                    cell_text.endswith(':') or  # Ends with colon
                    len(cell_text.split()) <= 3):  # Short text
                    header_indicators += 1
        
        # If more than half the cells look like headers
        return header_indicators > len(first_row) / 2
    
    def _check_document_metadata(self, metadata: Dict):
        required_metadata = ["title", "author", "subject"]
        
        for field in required_metadata:
            if not metadata.get(field) or metadata[field].strip() == "":
                # Skip title check here as it's handled by PDF18
                if field == "title":
                    continue
                    
                issue = AccessibilityIssue(
                    issue_id=f"metadata_{field}",
                    title=f"Missing Document {field.title()}",
                    description=f"Document metadata is missing {field}",
                    severity=Severity.INFO,
                    wcag_criteria="2.4.2 Page Titled",
                    wcag_level=WCAGLevel.A,
                    page_num=0,  # Document-level issue
                    bbox=(0, 0, 0, 0),
                    element_type="document",
                    current_value="",
                    suggested_fix=f"Add {field} to document metadata",
                    auto_fixable=False,
                    metadata={"field": field}
                )
                self.issues.append(issue)
    
    def _check_color_contrast(self, elements: List[PDFElement]):
        # Color contrast checking would require more advanced PDF parsing
        # This is a placeholder for future implementation
        pass
    
    def get_issues_by_severity(self, severity: Severity) -> List[AccessibilityIssue]:
        return [issue for issue in self.issues if issue.severity == severity]
    
    def get_issues_by_page(self, page_num: int) -> List[AccessibilityIssue]:
        return [issue for issue in self.issues if issue.page_num == page_num]
    
    def get_auto_fixable_issues(self) -> List[AccessibilityIssue]:
        return [issue for issue in self.issues if issue.auto_fixable]
    
    def get_issues_by_pdf_technique(self, technique_code: str) -> List[AccessibilityIssue]:
        """Get all issues related to a specific PDF technique"""
        return [issue for issue in self.issues if issue.pdf_technique == technique_code]
    
    def get_pdf_technique_summary(self) -> Dict[str, int]:
        """Get summary of issues by PDF technique"""
        technique_counts = {}
        for issue in self.issues:
            if issue.pdf_technique:
                technique_counts[issue.pdf_technique] = technique_counts.get(issue.pdf_technique, 0) + 1
        return technique_counts
    
    def generate_summary(self) -> Dict:
        critical_count = len(self.get_issues_by_severity(Severity.CRITICAL))
        warning_count = len(self.get_issues_by_severity(Severity.WARNING))
        info_count = len(self.get_issues_by_severity(Severity.INFO))
        auto_fixable_count = len(self.get_auto_fixable_issues())
        
        # Count PDF technique violations
        pdf_technique_violations = {}
        for issue in self.issues:
            if issue.pdf_technique:
                pdf_technique_violations[issue.pdf_technique] = pdf_technique_violations.get(issue.pdf_technique, 0) + 1
        
        return {
            "total_issues": len(self.issues),
            "critical_issues": critical_count,
            "warning_issues": warning_count,
            "info_issues": info_count,
            "auto_fixable_issues": auto_fixable_count,
            "compliance_score": self._calculate_compliance_score(),
            "pdf_technique_violations": pdf_technique_violations,
            "techniques_with_issues": len(pdf_technique_violations)
        }
    
    def _check_pdf2_bookmarks(self, analysis: Dict):
        """PDF2: Check for bookmarks in long documents"""
        total_pages = analysis.get("total_pages", 0)
        bookmarks = analysis.get("bookmarks", [])
        
        # Require bookmarks for documents longer than 10 pages
        if total_pages > 10 and len(bookmarks) == 0:
            technique = get_technique_by_code("PDF2")
            issue = AccessibilityIssue(
                issue_id="pdf2_missing_bookmarks",
                title="Missing Document Bookmarks",
                description=f"Document has {total_pages} pages but no bookmarks for navigation",
                severity=Severity.WARNING,
                wcag_criteria=technique.wcag_criteria,
                wcag_level=WCAGLevel.AA,
                page_num=0,
                bbox=(0, 0, 0, 0),
                element_type="document",
                current_value=f"No bookmarks in {total_pages}-page document",
                suggested_fix="Add hierarchical bookmarks based on document structure",
                auto_fixable=False,
                pdf_technique="PDF2",
                remediation_guidance=get_remediation_guidance("PDF2")
            )
            self.issues.append(issue)
    
    def _check_pdf3_reading_order_enhanced(self, analysis: Dict):
        """PDF3: Enhanced reading order validation"""
        reading_order = analysis.get("reading_order", [])
        if len(reading_order) < 2:
            return
        
        technique = get_technique_by_code("PDF3")
        
        # Check for complex layout issues that affect reading order
        for i in range(len(reading_order) - 1):
            current = reading_order[i]
            next_elem = reading_order[i + 1]
            
            # Enhanced logic for multi-column detection
            if (current.page_num == next_elem.page_num and
                current.bbox[0] > next_elem.bbox[2] and  # Current starts after next ends
                abs(current.bbox[1] - next_elem.bbox[1]) < 20):  # Similar Y position
                
                issue = AccessibilityIssue(
                    issue_id=f"pdf3_reading_order_multicolumn_{current.page_num}_{i}",
                    title="Multi-column Reading Order Issue",
                    description="Reading order may be incorrect in multi-column layout",
                    severity=Severity.WARNING,
                    wcag_criteria=technique.wcag_criteria,
                    wcag_level=WCAGLevel.A,
                    page_num=current.page_num,
                    bbox=current.bbox,
                    element_type=current.type,
                    current_value=f"Element order: '{current.content[:30]}...' before '{next_elem.content[:30]}...'",
                    suggested_fix="Verify and correct reading order for multi-column content",
                    auto_fixable=False,
                    pdf_technique="PDF3",
                    remediation_guidance=get_remediation_guidance("PDF3")
                )
                self.issues.append(issue)
    
    def _check_pdf4_decorative_images(self, images: List[PDFImage]):
        """PDF4: Check if decorative images are properly marked as artifacts"""
        technique = get_technique_by_code("PDF4")
        
        for image in images:
            # Heuristics to detect potentially decorative images
            is_likely_decorative = False
            
            # Check if image is very small (likely a bullet, separator, etc.)
            if image.pil_image:
                width = image.pil_image.width
                height = image.pil_image.height
                if width < 50 and height < 50:
                    is_likely_decorative = True
            
            # Check if image has generic name suggesting decoration
            if image.alt_text:
                decorative_keywords = ['decoration', 'separator', 'divider', 'spacer', 
                                      'bullet', 'arrow', 'background', 'watermark']
                if any(keyword in image.alt_text.lower() for keyword in decorative_keywords):
                    is_likely_decorative = True
            
            # If likely decorative but not marked as artifact
            if is_likely_decorative and not image.is_decorative:
                issue = AccessibilityIssue(
                    issue_id=f"pdf4_decorative_not_artifact_{image.page_num}_{image.image_id}",
                    title="Decorative Image Not Marked as Artifact",
                    description="Image appears to be decorative but is not marked as an artifact",
                    severity=Severity.WARNING,
                    wcag_criteria=technique.wcag_criteria,
                    wcag_level=WCAGLevel.A,
                    page_num=image.page_num,
                    bbox=image.bbox,
                    element_type="image",
                    current_value=f"Image {image.image_id}: {image.alt_text[:30] if image.alt_text else 'No alt'}",
                    suggested_fix="Mark decorative image as artifact using /Artifact tag",
                    auto_fixable=False,
                    pdf_technique="PDF4",
                    remediation_guidance=get_remediation_guidance("PDF4"),
                    metadata={
                        "image_id": image.image_id,
                        "image_width": image.pil_image.width if image.pil_image else 0,
                        "image_height": image.pil_image.height if image.pil_image else 0,
                        "is_decorative": image.is_decorative,
                        "likely_decorative": is_likely_decorative
                    }
                )
                self.issues.append(issue)
            
            # Check if non-decorative image is incorrectly marked as artifact
            elif not is_likely_decorative and image.is_decorative:
                issue = AccessibilityIssue(
                    issue_id=f"pdf4_content_marked_artifact_{image.page_num}_{image.image_id}",
                    title="Content Image Incorrectly Marked as Artifact",
                    description="Image appears to contain content but is marked as artifact",
                    severity=Severity.CRITICAL,
                    wcag_criteria=technique.wcag_criteria,
                    wcag_level=WCAGLevel.A,
                    page_num=image.page_num,
                    bbox=image.bbox,
                    element_type="image",
                    current_value=f"Image marked as artifact",
                    suggested_fix="Remove artifact marking and provide appropriate alt text",
                    auto_fixable=False,
                    pdf_technique="PDF4",
                    remediation_guidance=get_remediation_guidance("PDF4"),
                    metadata={
                        "image_id": image.image_id,
                        "image_width": image.pil_image.width if image.pil_image else 0,
                        "image_height": image.pil_image.height if image.pil_image else 0
                    }
                )
                self.issues.append(issue)
    
    def _check_pdf6_table_structure_enhanced(self, tables: List[PDFElement]):
        """PDF6: Enhanced table structure validation"""
        technique = get_technique_by_code("PDF6")
        
        for table in tables:
            table_data = table.metadata.get("data", [])
            if not table_data or len(table_data) < 2:
                continue
            
            # Check for proper header row
            has_headers = self._detect_table_headers(table_data)
            if not has_headers:
                issue = AccessibilityIssue(
                    issue_id=f"pdf6_table_no_headers_{table.page_num}_{table.metadata.get('table_id', 0)}",
                    title="Table Missing Proper Headers",
                    description="Table structure lacks proper header cells (TH elements)",
                    severity=Severity.CRITICAL,
                    wcag_criteria=technique.wcag_criteria,
                    wcag_level=WCAGLevel.A,
                    page_num=table.page_num,
                    bbox=table.bbox,
                    element_type="table",
                    current_value=f"Table with {len(table_data)} rows, no headers detected",
                    suggested_fix="Mark first row as headers using TH elements instead of TD",
                    auto_fixable=False,
                    pdf_technique="PDF6",
                    remediation_guidance=get_remediation_guidance("PDF6"),
                    metadata={"table_data": table_data[:3]}  # First 3 rows for analysis
                )
                self.issues.append(issue)
            
            # Check for complex table structures
            if len(table_data) > 10 or (table_data and len(table_data[0]) > 6):
                issue = AccessibilityIssue(
                    issue_id=f"pdf6_complex_table_{table.page_num}_{table.metadata.get('table_id', 0)}",
                    title="Complex Table Structure",
                    description="Large table may need additional accessibility markup",
                    severity=Severity.INFO,
                    wcag_criteria=technique.wcag_criteria,
                    wcag_level=WCAGLevel.A,
                    page_num=table.page_num,
                    bbox=table.bbox,
                    element_type="table",
                    current_value=f"Table: {len(table_data)} rows × {len(table_data[0]) if table_data else 0} columns",
                    suggested_fix="Consider adding table summary or caption for complex data",
                    auto_fixable=False,
                    pdf_technique="PDF6",
                    remediation_guidance=get_remediation_guidance("PDF6")
                )
                self.issues.append(issue)
    
    def _check_pdf7_scanned_content(self, scanned_pages: List[Dict]):
        """PDF7: Check for scanned content needing OCR"""
        technique = get_technique_by_code("PDF7")
        
        for page_info in scanned_pages:
            issue = AccessibilityIssue(
                issue_id=f"pdf7_scanned_page_{page_info['page_num']}",
                title="Scanned Page Needs OCR",
                description="Page appears to be scanned image without searchable text",
                severity=Severity.CRITICAL,
                wcag_criteria=technique.wcag_criteria,
                wcag_level=WCAGLevel.AA,
                page_num=page_info['page_num'],
                bbox=(0, 0, 595, 842),  # Full page
                element_type="page",
                current_value=f"Scanned page with {page_info['text_length']} chars of text",
                suggested_fix="Run OCR to create searchable text layer",
                auto_fixable=False,
                pdf_technique="PDF7",
                remediation_guidance=get_remediation_guidance("PDF7"),
                metadata={
                    "image_count": page_info.get('image_count', 0),
                    "image_coverage": page_info.get('image_coverage', 0),
                    "text_length": page_info.get('text_length', 0)
                }
            )
            self.issues.append(issue)
    
    def _check_pdf10_form_labels(self, form_fields: List[Dict]):
        """PDF10: Check form field labels"""
        technique = get_technique_by_code("PDF10")
        
        for field in form_fields:
            field_name = field.get('field_name', '')
            field_label = field.get('field_label', '')
            tooltip = field.get('tooltip', '')
            
            # Check if field has adequate labeling
            if not field_label and not tooltip and not field_name:
                issue = AccessibilityIssue(
                    issue_id=f"pdf10_missing_label_{field['page_num']}_{field_name or 'unnamed'}",
                    title="Form Field Missing Label",
                    description="Interactive form control lacks descriptive label",
                    severity=Severity.CRITICAL,
                    wcag_criteria=technique.wcag_criteria,
                    wcag_level=WCAGLevel.A,
                    page_num=field['page_num'],
                    bbox=field['bbox'],
                    element_type="form_field",
                    current_value=f"{field.get('field_type', 'unknown')} field without label",
                    suggested_fix="Add descriptive label using /TU (tooltip) or adjacent text",
                    auto_fixable=False,
                    pdf_technique="PDF10",
                    remediation_guidance=get_remediation_guidance("PDF10"),
                    metadata=field
                )
                self.issues.append(issue)
    
    def _check_pdf11_link_structure(self, links: List[Dict]):
        """PDF11: Check link structure and text"""
        technique = get_technique_by_code("PDF11")
        
        for link in links:
            link_text = link.get('link_text', '').strip()
            uri = link.get('uri', '')
            
            # Check for empty or non-descriptive link text
            if not link_text:
                issue = AccessibilityIssue(
                    issue_id=f"pdf11_empty_link_text_{link['page_num']}",
                    title="Link Missing Descriptive Text",
                    description="Link does not have accessible text content",
                    severity=Severity.CRITICAL,
                    wcag_criteria=technique.wcag_criteria,
                    wcag_level=WCAGLevel.A,
                    page_num=link['page_num'],
                    bbox=link['bbox'],
                    element_type="link",
                    current_value=f"Link to: {uri[:50]}...",
                    suggested_fix="Add descriptive text or /Alt entry for link",
                    auto_fixable=False,
                    pdf_technique="PDF11",
                    remediation_guidance=get_remediation_guidance("PDF11"),
                    metadata=link
                )
                self.issues.append(issue)
            elif link_text.lower() in ['click here', 'read more', 'here', 'more', 'link']:
                issue = AccessibilityIssue(
                    issue_id=f"pdf11_generic_link_text_{link['page_num']}",
                    title="Generic Link Text",
                    description="Link text is not descriptive of the destination",
                    severity=Severity.WARNING,
                    wcag_criteria=technique.wcag_criteria,
                    wcag_level=WCAGLevel.A,
                    page_num=link['page_num'],
                    bbox=link['bbox'],
                    element_type="link",
                    current_value=f"Link text: '{link_text}'",
                    suggested_fix="Use descriptive link text that explains the destination",
                    auto_fixable=False,
                    pdf_technique="PDF11",
                    remediation_guidance=get_remediation_guidance("PDF11")
                )
                self.issues.append(issue)
    
    def _check_pdf12_form_name_role_value(self, form_fields: List[Dict]):
        """PDF12: Check form fields have name, role, value information"""
        technique = get_technique_by_code("PDF12")
        
        for field in form_fields:
            issues_found = []
            
            # Check Name (accessible name)
            if not field.get('field_name') and not field.get('field_label') and not field.get('tooltip'):
                issues_found.append("missing accessible name")
            
            # Check Role (field type)
            if not field.get('field_type') or field.get('field_type') == 'unknown':
                issues_found.append("missing or unknown role")
            
            # Check Value (for filled fields, ensure it's accessible)
            field_value = field.get('field_value', '')
            if field_value and field.get('field_type') == 'password':
                # Password fields should not expose values, this is correct
                pass
            
            if issues_found:
                issue = AccessibilityIssue(
                    issue_id=f"pdf12_incomplete_field_info_{field['page_num']}_{field.get('field_name', 'unnamed')}",
                    title="Form Field Missing Accessibility Information",
                    description=f"Form field lacks: {', '.join(issues_found)}",
                    severity=Severity.CRITICAL,
                    wcag_criteria=technique.wcag_criteria,
                    wcag_level=WCAGLevel.A,
                    page_num=field['page_num'],
                    bbox=field['bbox'],
                    element_type="form_field",
                    current_value=f"{field.get('field_type', 'unknown')} field: {field.get('field_name', 'unnamed')}",
                    suggested_fix="Ensure field has name (/T), role (/FT), and accessible value (/V)",
                    auto_fixable=False,
                    pdf_technique="PDF12",
                    remediation_guidance=get_remediation_guidance("PDF12"),
                    metadata=field
                )
                self.issues.append(issue)
    
    def _check_pdf16_document_language(self, analysis: Dict):
        """PDF16: Check document language setting"""
        technique = get_technique_by_code("PDF16")
        document_language = analysis.get("document_language", "")
        
        if not document_language or document_language == "unknown":
            issue = AccessibilityIssue(
                issue_id="pdf16_missing_document_language",
                title="Document Language Not Specified",
                description="Document does not have language specified in /Lang entry",
                severity=Severity.WARNING,
                wcag_criteria=technique.wcag_criteria,
                wcag_level=WCAGLevel.A,
                page_num=0,
                bbox=(0, 0, 0, 0),
                element_type="document",
                current_value="No language specified",
                suggested_fix="Set document language using /Lang entry in document catalog",
                auto_fixable=False,
                pdf_technique="PDF16",
                remediation_guidance=get_remediation_guidance("PDF16")
            )
            self.issues.append(issue)
    
    def _check_pdf18_document_title(self, metadata: Dict):
        """PDF18: Check document title in metadata"""
        technique = get_technique_by_code("PDF18")
        title = metadata.get("title", "").strip()
        
        if not title:
            issue = AccessibilityIssue(
                issue_id="pdf18_missing_document_title",
                title="Document Title Missing",
                description="Document metadata lacks descriptive title",
                severity=Severity.WARNING,
                wcag_criteria=technique.wcag_criteria,
                wcag_level=WCAGLevel.A,
                page_num=0,
                bbox=(0, 0, 0, 0),
                element_type="document",
                current_value="No title in document metadata",
                suggested_fix="Add descriptive title in document information dictionary",
                auto_fixable=False,
                pdf_technique="PDF18",
                remediation_guidance=get_remediation_guidance("PDF18")
            )
            self.issues.append(issue)
        elif len(title) < 5 or title.lower() in ['untitled', 'document', 'pdf', 'new document']:
            issue = AccessibilityIssue(
                issue_id="pdf18_generic_document_title",
                title="Document Title Too Generic",
                description="Document title is not descriptive enough",
                severity=Severity.INFO,
                wcag_criteria=technique.wcag_criteria,
                wcag_level=WCAGLevel.A,
                page_num=0,
                bbox=(0, 0, 0, 0),
                element_type="document",
                current_value=f"Current title: '{title}'",
                suggested_fix="Use descriptive, meaningful document title",
                auto_fixable=False,
                pdf_technique="PDF18",
                remediation_guidance=get_remediation_guidance("PDF18")
            )
            self.issues.append(issue)
    
    def _check_pdf21_list_structure(self, lists: List[Dict]):
        """PDF21: Check list structure markup"""
        technique = get_technique_by_code("PDF21")
        
        for list_info in lists:
            items = list_info.get('items', [])
            list_type = list_info.get('list_type', 'unknown')
            
            # Check for lists that should be properly marked up
            if len(items) >= 3:  # Lists with 3+ items should be properly structured
                issue = AccessibilityIssue(
                    issue_id=f"pdf21_unstructured_list_{list_info['page_num']}_{list_info['list_id']}",
                    title="List Needs Proper Structure Markup",
                    description=f"{list_type.title()} list should use L, LI, Lbl, LBody structure elements",
                    severity=Severity.WARNING,
                    wcag_criteria=technique.wcag_criteria,
                    wcag_level=WCAGLevel.A,
                    page_num=list_info['page_num'],
                    bbox=list_info['bbox'],
                    element_type="list",
                    current_value=f"{list_type} list with {len(items)} items",
                    suggested_fix="Mark up list using proper L (list), LI (list item) structure elements",
                    auto_fixable=False,
                    pdf_technique="PDF21",
                    remediation_guidance=get_remediation_guidance("PDF21"),
                    metadata={
                        "list_type": list_type,
                        "items_count": len(items),
                        "first_few_items": [item['content'][:50] for item in items[:3]]
                    }
                )
                self.issues.append(issue)
    
    def _calculate_compliance_score(self) -> float:
        if not self.issues:
            return 100.0
        
        # Enhanced scoring that considers PDF technique compliance
        total_deductions = 0
        pdf_technique_issues = 0
        
        for issue in self.issues:
            # Base deduction by severity
            if issue.severity == Severity.CRITICAL:
                deduction = 10
            elif issue.severity == Severity.WARNING:
                deduction = 5
            else:  # INFO
                deduction = 1
            
            # Additional weight for PDF technique violations
            if issue.pdf_technique:
                pdf_technique_issues += 1
                deduction = int(deduction * 1.2)  # 20% penalty for technique violations
            
            total_deductions += deduction
        
        score = max(0, 100 - total_deductions)
        return round(score, 1)
    
    def validate_with_verapdf(self, pdf_path: str) -> Optional[VeraPDFValidationResult]:
        """Perform final PDF/UA validation using veraPDF"""
        if not self.verapdf_validator or not self.verapdf_validator.is_available():
            logger.warning("veraPDF not available for final validation")
            return None
        
        try:
            logger.info(f"Running veraPDF validation on {pdf_path}")
            result = self.verapdf_validator.validate_pdf_ua(pdf_path)
            
            if result:
                # Add veraPDF-specific issues to our issue list
                self._add_verapdf_issues(result, pdf_path)
                logger.info(f"veraPDF validation complete: {result.get_compliance_score():.1f}% compliant")
            
            return result
            
        except Exception as e:
            logger.error(f"veraPDF validation failed: {e}")
            return None
    
    def _add_verapdf_issues(self, verapdf_result: VeraPDFValidationResult, pdf_path: str):
        """Add veraPDF validation failures as accessibility issues"""
        if not verapdf_result.failed_rules:
            return
        
        # Get critical failures and convert to our issue format
        critical_failures = verapdf_result.get_critical_failures()
        
        for i, failed_rule in enumerate(critical_failures):
            # Map veraPDF rule to our issue format
            issue_id = f"verapdf_{failed_rule.rule_id}_{i}"
            
            # Determine severity based on rule type
            severity = self._map_verapdf_severity(failed_rule)
            
            # Map to WCAG criteria
            wcag_criteria = self._map_verapdf_to_wcag(failed_rule)
            
            # Create accessibility issue
            issue = AccessibilityIssue(
                issue_id=issue_id,
                title=f"PDF/UA Validation Failure: {failed_rule.rule_id}",
                description=failed_rule.message,
                severity=severity,
                wcag_criteria=wcag_criteria,
                wcag_level=self.wcag_level,
                page_num=failed_rule.page_number or 0,
                bbox=(0, 0, 100, 100),  # Default bbox for document-level issues
                element_type="document",
                current_value=f"veraPDF rule {failed_rule.rule_id} failed",
                suggested_fix=self._get_verapdf_remediation(failed_rule),
                auto_fixable=False,
                pdf_technique="PDF/UA",
                remediation_guidance={
                    "description": failed_rule.message,
                    "rule_id": failed_rule.rule_id,
                    "object_type": failed_rule.object_type,
                    "location": failed_rule.location
                }
            )
            
            self.issues.append(issue)
        
        logger.info(f"Added {len(critical_failures)} veraPDF validation issues")
    
    def _map_verapdf_severity(self, rule: 'VeraPDFRule') -> Severity:
        """Map veraPDF rule failure to severity level"""
        # Critical PDF/UA requirements
        critical_keywords = [
            "structure", "tagged", "language", "title", 
            "alternative", "description", "role"
        ]
        
        rule_text = (rule.message + " " + rule.object_type).lower()
        
        if any(keyword in rule_text for keyword in critical_keywords):
            return Severity.CRITICAL
        else:
            return Severity.WARNING
    
    def _map_verapdf_to_wcag(self, rule: 'VeraPDFRule') -> str:
        """Map veraPDF rule to WCAG success criteria"""
        rule_text = (rule.message + " " + rule.object_type).lower()
        
        # Common mappings
        if "alternative" in rule_text or "description" in rule_text:
            return "1.1.1 Non-text Content"
        elif "language" in rule_text:
            return "3.1.1 Language of Page"
        elif "title" in rule_text:
            return "2.4.2 Page Titled"
        elif "structure" in rule_text or "heading" in rule_text:
            return "1.3.1 Info and Relationships"
        elif "table" in rule_text:
            return "1.3.1 Info and Relationships"
        elif "list" in rule_text:
            return "1.3.1 Info and Relationships"
        elif "form" in rule_text or "field" in rule_text:
            return "3.3.2 Labels or Instructions"
        elif "reading order" in rule_text or "sequence" in rule_text:
            return "1.3.2 Meaningful Sequence"
        else:
            return "4.1.2 Name, Role, Value"
    
    def _get_verapdf_remediation(self, rule: 'VeraPDFRule') -> str:
        """Get remediation suggestion for veraPDF rule failure"""
        rule_text = rule.message.lower()
        
        if "alternative text" in rule_text:
            return "Add alternative text descriptions for images using /Alt entry"
        elif "language" in rule_text:
            return "Set document language in PDF catalog using /Lang entry"
        elif "title" in rule_text:
            return "Add descriptive title to document metadata"
        elif "structure" in rule_text:
            return "Ensure proper PDF structure tree with appropriate tags"
        elif "tagged" in rule_text:
            return "Mark content with proper structure tags or as artifacts"
        elif "table" in rule_text:
            return "Add proper table structure with TH header cells"
        elif "form" in rule_text:
            return "Add labels to form fields using /TU or adjacent text"
        else:
            return f"Fix PDF/UA compliance issue: {rule.message}"
    
    def generate_comprehensive_summary(self, verapdf_result: Optional[VeraPDFValidationResult] = None) -> Dict:
        """Generate comprehensive summary including veraPDF results"""
        base_summary = self.generate_summary()
        
        if verapdf_result:
            base_summary.update({
                "verapdf_validation": {
                    "is_compliant": verapdf_result.is_compliant,
                    "compliance_score": verapdf_result.get_compliance_score(),
                    "total_checks": verapdf_result.total_checks,
                    "passed_checks": verapdf_result.passed_checks,
                    "failed_checks": verapdf_result.failed_checks,
                    "profile": verapdf_result.profile_name,
                    "category_breakdown": verapdf_result.summary_by_category
                },
                "final_compliance_status": "PDF/UA Compliant" if verapdf_result.is_compliant else "Not PDF/UA Compliant"
            })
            
            # Update overall compliance score with veraPDF results
            if verapdf_result.total_checks > 0:
                # Weighted average of our internal score and veraPDF score
                internal_weight = 0.6
                verapdf_weight = 0.4
                
                combined_score = (
                    base_summary["compliance_score"] * internal_weight +
                    verapdf_result.get_compliance_score() * verapdf_weight
                )
                base_summary["combined_compliance_score"] = round(combined_score, 1)
        
        return base_summary