from enum import Enum
from typing import Dict, List, Tuple
from dataclasses import dataclass

@dataclass 
class PDFTechniqueInfo:
    """Information about a specific PDF technique"""
    code: str
    title: str
    wcag_criteria: str
    wcag_level: str
    description: str
    implementation_notes: str

class PDFTechnique(Enum):
    """PDF accessibility techniques from W3C WCAG 2.0 Techniques"""
    
    PDF1 = PDFTechniqueInfo(
        code="PDF1",
        title="Applying text alternatives to images with the Alt entry",
        wcag_criteria="1.1.1 Non-text Content",
        wcag_level="A",
        description="Provide text alternatives for images via an /Alt entry in the property list for a Tag",
        implementation_notes="Use /Alt entry in image properties to provide descriptive text alternatives"
    )
    
    PDF2 = PDFTechniqueInfo(
        code="PDF2", 
        title="Creating bookmarks in PDF documents",
        wcag_criteria="2.4.5 Multiple Ways",
        wcag_level="AA",
        description="Make it possible for users to locate content using bookmarks in long documents",
        implementation_notes="Create hierarchical bookmarks from document structure or table of contents"
    )
    
    PDF3 = PDFTechniqueInfo(
        code="PDF3",
        title="Ensuring correct tab and reading order in PDF documents", 
        wcag_criteria="1.3.2 Meaningful Sequence",
        wcag_level="A",
        description="Ensure users can navigate through content in a logical order",
        implementation_notes="Set proper StructTreeRoot and reading order in PDF structure tree"
    )
    
    PDF4 = PDFTechniqueInfo(
        code="PDF4",
        title="Hiding decorative images with the Artifact tag in PDF documents",
        wcag_criteria="1.1.1 Non-text Content", 
        wcag_level="A",
        description="Mark purely decorative images so they can be ignored by Assistive Technology",
        implementation_notes="Use /Artifact tag to exclude decorative elements from document structure"
    )
    
    PDF5 = PDFTechniqueInfo(
        code="PDF5",
        title="Indicating required form fields in PDF forms",
        wcag_criteria="3.3.2 Labels or Instructions",
        wcag_level="A", 
        description="Notify users when a field that must be completed has not been completed",
        implementation_notes="Use visual and programmatic indicators for required form fields"
    )
    
    PDF6 = PDFTechniqueInfo(
        code="PDF6",
        title="Using table elements for table markup in PDF Documents",
        wcag_criteria="1.3.1 Info and Relationships",
        wcag_level="A",
        description="Mark up tables so they are recognized by assistive technology",
        implementation_notes="Use Table, TR, TH, TD structure elements for proper table markup"
    )
    
    PDF7 = PDFTechniqueInfo(
        code="PDF7",
        title="Performing OCR on a scanned PDF document to provide actual text",
        wcag_criteria="1.4.5 Images of Text",
        wcag_level="AA",
        description="Ensure visually rendered text can be perceived without visual presentation interfering",
        implementation_notes="Run OCR on scanned documents to create searchable text layer"
    )
    
    PDF8 = PDFTechniqueInfo(
        code="PDF8",
        title="Providing definitions for abbreviations via an E entry for a structure element",
        wcag_criteria="3.1.4 Abbreviations",
        wcag_level="AAA",
        description="Provide expansion or definition of abbreviations",
        implementation_notes="Use /E entry to define abbreviations on first occurrence"
    )
    
    PDF9 = PDFTechniqueInfo(
        code="PDF9", 
        title="Providing headings by marking content with heading tags in PDF documents",
        wcag_criteria="1.3.1 Info and Relationships",
        wcag_level="A",
        description="Mark headings so they are recognized by assistive technologies",
        implementation_notes="Use H1-H6 structure elements to mark heading hierarchy"
    )
    
    PDF10 = PDFTechniqueInfo(
        code="PDF10",
        title="Providing labels for interactive form controls in PDF documents",
        wcag_criteria="1.3.1 Info and Relationships",
        wcag_level="A",
        description="Ensure form fields have clear, descriptive labels",
        implementation_notes="Associate form fields with descriptive labels using /TU or /T entries"
    )
    
    PDF11 = PDFTechniqueInfo(
        code="PDF11",
        title="Providing links and link text using the Link annotation and the /Link structure element",
        wcag_criteria="2.4.4 Link Purpose (In Context)",
        wcag_level="A", 
        description="Create meaningful, descriptive hyperlinks in PDF documents",
        implementation_notes="Use Link annotation with /Link structure element for semantic links"
    )
    
    PDF12 = PDFTechniqueInfo(
        code="PDF12",
        title="Providing name, role, value information for form fields in PDF documents",
        wcag_criteria="4.1.2 Name, Role, Value",
        wcag_level="A",
        description="Ensure form controls provide complete accessibility information", 
        implementation_notes="Include name (/T), role (/FT), and value (/V) for all form fields"
    )
    
    PDF13 = PDFTechniqueInfo(
        code="PDF13",
        title="Providing replacement text using the /Alt entry for links in PDF documents",
        wcag_criteria="2.4.4 Link Purpose (In Context)",
        wcag_level="A",
        description="Add alternative text for links when visual context is unclear",
        implementation_notes="Use /Alt entry in link properties for descriptive link text"
    )
    
    PDF14 = PDFTechniqueInfo(
        code="PDF14",
        title="Providing running headers and footers in PDF documents",
        wcag_criteria="3.2.3 Consistent Navigation", 
        wcag_level="AA",
        description="Create consistent page navigation elements marked as artifacts",
        implementation_notes="Mark headers/footers as artifacts to prevent screen reader interference"
    )
    
    PDF15 = PDFTechniqueInfo(
        code="PDF15",
        title="Providing submit buttons with the submit-form action in PDF forms",
        wcag_criteria="3.2.2 On Input",
        wcag_level="A",
        description="Ensure form submission functionality is properly implemented",
        implementation_notes="Add submit button with proper submit-form action for form processing"
    )
    
    PDF16 = PDFTechniqueInfo(
        code="PDF16", 
        title="Setting the default language using the /Lang entry in the document catalog",
        wcag_criteria="3.1.1 Language of Page",
        wcag_level="A",
        description="Specify document language for assistive technology",
        implementation_notes="Set /Lang entry in document catalog to specify primary language"
    )
    
    PDF17 = PDFTechniqueInfo(
        code="PDF17",
        title="Specifying consistent page numbering for PDF documents",
        wcag_criteria="3.2.3 Consistent Navigation",
        wcag_level="AA", 
        description="Ensure predictable page numbering throughout document",
        implementation_notes="Implement consistent page number formatting and placement"
    )
    
    PDF18 = PDFTechniqueInfo(
        code="PDF18",
        title="Specifying the document title using the Title entry in the document information dictionary",
        wcag_criteria="2.4.2 Page Titled",
        wcag_level="A",
        description="Provide meaningful document title in metadata",
        implementation_notes="Set Title entry in document information dictionary"
    )
    
    PDF19 = PDFTechniqueInfo(
        code="PDF19",
        title="Specifying the language for a passage or phrase with the Lang entry",
        wcag_criteria="3.1.2 Language of Parts", 
        wcag_level="AA",
        description="Indicate language changes within document content",
        implementation_notes="Use Lang entry for content sections in different languages"
    )
    
    PDF20 = PDFTechniqueInfo(
        code="PDF20",
        title="Using Adobe Acrobat Pro's Table Editor to repair mistagged tables",
        wcag_criteria="1.3.1 Info and Relationships",
        wcag_level="A",
        description="Correct table structure and tagging issues",
        implementation_notes="Use specialized tools to fix table semantics and accessibility"
    )
    
    PDF21 = PDFTechniqueInfo(
        code="PDF21", 
        title="Using List tags for lists in PDF documents",
        wcag_criteria="1.3.1 Info and Relationships", 
        wcag_level="A",
        description="Properly mark up lists with semantic structure",
        implementation_notes="Use L, LI, Lbl, LBody structure elements for list markup"
    )
    
    PDF22 = PDFTechniqueInfo(
        code="PDF22",
        title="Indicating when user input falls outside the required format or values",
        wcag_criteria="3.3.1 Error Identification",
        wcag_level="A",
        description="Provide validation and error messaging for form fields", 
        implementation_notes="Implement form validation with clear error descriptions"
    )
    
    PDF23 = PDFTechniqueInfo(
        code="PDF23",
        title="Providing interactive form controls in PDF documents",
        wcag_criteria="4.1.2 Name, Role, Value",
        wcag_level="A",
        description="Create accessible and usable PDF forms",
        implementation_notes="Implement proper form controls with full accessibility support"
    )

class PDFStructureType(Enum):
    """PDF structure element types"""
    ARTIFACT = "Artifact"
    DOCUMENT = "Document" 
    PART = "Part"
    SECTION = "Sect"
    DIVISION = "Div"
    PARAGRAPH = "P"
    HEADING_1 = "H1"
    HEADING_2 = "H2" 
    HEADING_3 = "H3"
    HEADING_4 = "H4"
    HEADING_5 = "H5"
    HEADING_6 = "H6"
    LIST = "L"
    LIST_ITEM = "LI"
    LIST_LABEL = "Lbl"
    LIST_BODY = "LBody"
    TABLE = "Table"
    TABLE_ROW = "TR"
    TABLE_HEADER = "TH"
    TABLE_DATA = "TD"
    THEAD = "THead"
    TBODY = "TBody"
    TFOOT = "TFoot"
    CAPTION = "Caption"
    LINK = "Link"
    ANNOTATION = "Annot"
    FORM = "Form"
    FIGURE = "Figure"
    FORMULA = "Formula"
    SPAN = "Span"
    QUOTE = "Quote"
    NOTE = "Note"
    REFERENCE = "Reference"
    BIBLIOGRAPHY = "BibEntry"
    CODE = "Code"

class PDFComplianceLevel(Enum):
    """PDF accessibility compliance levels"""
    BASIC = "basic"           # Essential accessibility features
    STANDARD = "standard"     # WCAG 2.1 Level AA compliance  
    COMPREHENSIVE = "comprehensive"  # Full WCAG 2.2 + PDF/UA compliance

def get_technique_by_code(code: str) -> PDFTechniqueInfo:
    """Get PDF technique info by code (e.g., 'PDF1')"""
    for technique in PDFTechnique:
        if technique.value.code == code:
            return technique.value
    raise ValueError(f"Unknown PDF technique code: {code}")

def get_techniques_by_wcag_level(level: str) -> List[PDFTechniqueInfo]:
    """Get all techniques for a specific WCAG level"""
    return [technique.value for technique in PDFTechnique 
            if technique.value.wcag_level == level]

def get_high_priority_techniques() -> List[str]:
    """Get list of high-priority technique codes"""
    return ["PDF1", "PDF3", "PDF6", "PDF9", "PDF10", "PDF11", "PDF12", "PDF16", "PDF18"]

def get_techniques_by_criteria(criteria: str) -> List[PDFTechniqueInfo]:
    """Get techniques that address a specific WCAG success criteria"""
    return [technique.value for technique in PDFTechnique 
            if criteria in technique.value.wcag_criteria]

def get_remediation_guidance(technique_code: str) -> Dict[str, str]:
    """Get detailed remediation guidance for a technique"""
    technique = get_technique_by_code(technique_code)
    
    remediation_guides = {
        "PDF1": {
            "description": "Add alternative text to images using /Alt property",
            "steps": [
                "1. Identify images missing alt text",
                "2. Add /Alt entry to image properties", 
                "3. Provide descriptive alternative text",
                "4. Test with screen reader"
            ],
            "tools": "PDF authoring software, Adobe Acrobat Pro",
            "testing": "Use screen reader to verify alt text is announced"
        },
        "PDF3": {
            "description": "Ensure logical reading order and tab sequence",
            "steps": [
                "1. Review document structure tree",
                "2. Set proper reading order",
                "3. Verify tab sequence for interactive elements",
                "4. Test keyboard navigation"
            ],
            "tools": "Adobe Acrobat Pro, PDF accessibility checkers",
            "testing": "Navigate with keyboard only, use screen reader"
        },
        "PDF6": {
            "description": "Use proper table markup with headers",
            "steps": [
                "1. Tag table with Table structure element",
                "2. Mark header cells with TH tags",
                "3. Mark data cells with TD tags", 
                "4. Ensure proper row/column associations"
            ],
            "tools": "Adobe Acrobat Pro Table Editor",
            "testing": "Verify table navigation with screen reader"
        }
        # Add more remediation guides as needed
    }
    
    return remediation_guides.get(technique_code, {
        "description": technique.description,
        "steps": [technique.implementation_notes],
        "tools": "PDF authoring software",
        "testing": "Manual accessibility testing required"
    })