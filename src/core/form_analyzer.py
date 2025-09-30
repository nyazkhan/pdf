import logging
from typing import List, Dict, Tuple, Optional
import re
from enum import Enum

logger = logging.getLogger(__name__)

class FormFieldType(Enum):
    """PDF form field types"""
    TEXT = "text"
    PASSWORD = "password"
    TEXTAREA = "textarea"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    DROPDOWN = "dropdown"
    LISTBOX = "listbox"
    BUTTON = "button"
    SUBMIT = "submit"
    RESET = "reset"
    SIGNATURE = "signature"
    UNKNOWN = "unknown"

class FormValidationLevel(Enum):
    """Form validation levels"""
    BASIC = "basic"
    STANDARD = "standard"
    COMPREHENSIVE = "comprehensive"

class FormAnalyzer:
    """Comprehensive form accessibility analyzer for PDF techniques PDF5, PDF10, PDF12, PDF15, PDF22, PDF23"""
    
    def __init__(self, validation_level: FormValidationLevel = FormValidationLevel.STANDARD):
        self.validation_level = validation_level
        self.issues = []
    
    def analyze_forms(self, form_fields: List[Dict], analysis_context: Dict = None) -> Dict:
        """Analyze all form fields for accessibility compliance"""
        if not form_fields:
            return {
                "total_fields": 0,
                "issues": [],
                "field_types": {},
                "accessibility_score": 100.0,
                "recommendations": []
            }
        
        self.issues = []
        analysis_context = analysis_context or {}
        
        # Analyze each form field
        field_analysis = {}
        field_types = {}
        
        for field in form_fields:
            field_id = f"{field.get('page_num', 0)}_{field.get('field_name', 'unnamed')}"
            field_analysis[field_id] = self._analyze_single_field(field)
            
            field_type = field.get('field_type', 'unknown')
            field_types[field_type] = field_types.get(field_type, 0) + 1
        
        # Analyze form-level patterns
        form_level_issues = self._analyze_form_patterns(form_fields)
        self.issues.extend(form_level_issues)
        
        # Calculate accessibility score
        accessibility_score = self._calculate_form_accessibility_score()
        
        # Generate recommendations
        recommendations = self._generate_form_recommendations(form_fields)
        
        return {
            "total_fields": len(form_fields),
            "field_analysis": field_analysis,
            "field_types": field_types,
            "issues": self.issues,
            "accessibility_score": accessibility_score,
            "recommendations": recommendations,
            "validation_level": self.validation_level.value
        }
    
    def _analyze_single_field(self, field: Dict) -> Dict:
        """Analyze a single form field for accessibility compliance"""
        field_issues = []
        
        # PDF10: Check for field labels
        label_issues = self._check_field_labeling(field)
        field_issues.extend(label_issues)
        
        # PDF12: Check name, role, value information
        nrv_issues = self._check_name_role_value(field)
        field_issues.extend(nrv_issues)
        
        # PDF5: Check required field indicators
        required_issues = self._check_required_field_indicators(field)
        field_issues.extend(required_issues)
        
        # PDF22: Check validation and error handling
        validation_issues = self._check_field_validation(field)
        field_issues.extend(validation_issues)
        
        # PDF23: Check interactive control accessibility
        interaction_issues = self._check_interactive_accessibility(field)
        field_issues.extend(interaction_issues)
        
        self.issues.extend(field_issues)
        
        return {
            "field_name": field.get('field_name', ''),
            "field_type": field.get('field_type', 'unknown'),
            "issues_count": len(field_issues),
            "issues": field_issues,
            "accessibility_score": self._calculate_field_score(field, field_issues)
        }
    
    def _check_field_labeling(self, field: Dict) -> List[Dict]:
        """PDF10: Check form field labeling"""
        issues = []
        
        field_name = field.get('field_name', '')
        field_label = field.get('field_label', '')
        tooltip = field.get('tooltip', '')
        
        # Check if field has any form of labeling
        has_label = bool(field_label or tooltip or field_name)
        
        if not has_label:
            issues.append({
                "issue_type": "PDF10_missing_label",
                "severity": "critical",
                "description": "Form field lacks accessible label",
                "suggestion": "Add field label using /TU (tooltip) or /T (field name) entry"
            })
        elif field_label and len(field_label.strip()) < 2:
            issues.append({
                "issue_type": "PDF10_inadequate_label",
                "severity": "warning", 
                "description": "Form field label is too short to be descriptive",
                "suggestion": "Use more descriptive label text"
            })
        
        # Check for generic or non-descriptive labels
        if field_label:
            generic_labels = ['field', 'input', 'text', 'box', 'enter', 'type', 'click']
            if any(generic in field_label.lower() for generic in generic_labels):
                issues.append({
                    "issue_type": "PDF10_generic_label",
                    "severity": "warning",
                    "description": "Form field label is generic and not descriptive",
                    "suggestion": "Use specific, descriptive label that explains the field's purpose"
                })
        
        return issues
    
    def _check_name_role_value(self, field: Dict) -> List[Dict]:
        """PDF12: Check name, role, value information"""
        issues = []
        
        # Check Name (accessible name)
        name_sources = [
            field.get('field_name', ''),
            field.get('field_label', ''),
            field.get('tooltip', '')
        ]
        has_accessible_name = any(source.strip() for source in name_sources)
        
        if not has_accessible_name:
            issues.append({
                "issue_type": "PDF12_missing_name",
                "severity": "critical",
                "description": "Form field lacks accessible name",
                "suggestion": "Provide accessible name via /T, /TU, or adjacent label"
            })
        
        # Check Role (field type)
        field_type = field.get('field_type', '')
        if not field_type or field_type == 'unknown':
            issues.append({
                "issue_type": "PDF12_missing_role",
                "severity": "critical",
                "description": "Form field type (role) is not specified",
                "suggestion": "Set proper field type using /FT entry"
            })
        
        # Check Value accessibility (for certain field types)
        field_value = field.get('field_value', '')
        if field_type in ['dropdown', 'listbox'] and not field_value:
            # These field types should have selectable options
            issues.append({
                "issue_type": "PDF12_missing_options",
                "severity": "warning",
                "description": f"{field_type} field should have accessible options/values",
                "suggestion": "Ensure field options are properly defined and accessible"
            })
        
        return issues
    
    def _check_required_field_indicators(self, field: Dict) -> List[Dict]:
        """PDF5: Check required field indicators"""
        issues = []
        
        is_required = field.get('is_required', False)
        field_name = field.get('field_name', '')
        field_label = field.get('field_label', '')
        tooltip = field.get('tooltip', '')
        
        if is_required:
            # Check if required status is clearly indicated
            required_indicators = ['*', 'required', 'mandatory', 'must', 'need']
            text_to_check = f"{field_name} {field_label} {tooltip}".lower()
            
            has_visual_indicator = any(indicator in text_to_check for indicator in required_indicators)
            
            if not has_visual_indicator:
                issues.append({
                    "issue_type": "PDF5_missing_required_indicator",
                    "severity": "warning",
                    "description": "Required field lacks clear visual indicator",
                    "suggestion": "Add visual indicator (e.g., asterisk) and explanatory text for required fields"
                })
        
        # Check for fields that might be required but not marked as such
        if field_name and any(keyword in field_name.lower() for keyword in ['email', 'name', 'phone', 'address']):
            if not is_required:
                issues.append({
                    "issue_type": "PDF5_unmarked_required_field",
                    "severity": "info",
                    "description": "Field appears to be important but not marked as required",
                    "suggestion": "Verify if field should be marked as required"
                })
        
        return issues
    
    def _check_field_validation(self, field: Dict) -> List[Dict]:
        """PDF22: Check field validation and error handling"""
        issues = []
        
        field_type = field.get('field_type', '')
        field_name = field.get('field_name', '')
        
        # Check for fields that typically need format validation
        validation_needed_fields = {
            'email': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
            'phone': r'^[\d\s\-\(\)\+\.]+$',
            'date': r'^\d{1,2}\/\d{1,2}\/\d{4}$',
            'time': r'^\d{1,2}:\d{2}(\s?(AM|PM))?$',
            'url': r'^https?:\/\/.+',
            'zip': r'^\d{5}(-\d{4})?$'
        }
        
        if field_name:
            field_name_lower = field_name.lower()
            needs_validation = False
            
            for field_pattern, regex_pattern in validation_needed_fields.items():
                if field_pattern in field_name_lower:
                    needs_validation = True
                    break
            
            if needs_validation:
                issues.append({
                    "issue_type": "PDF22_validation_needed",
                    "severity": "info",
                    "description": f"Field '{field_name}' may need format validation",
                    "suggestion": "Add client-side validation with clear error messages"
                })
        
        # Check for password fields without confirmation
        if field_type == 'password' and 'confirm' not in field_name.lower():
            issues.append({
                "issue_type": "PDF22_password_confirmation",
                "severity": "info",
                "description": "Password field should have confirmation field",
                "suggestion": "Add password confirmation field for better user experience"
            })
        
        return issues
    
    def _check_interactive_accessibility(self, field: Dict) -> List[Dict]:
        """PDF23: Check interactive form control accessibility"""
        issues = []

        field_type = field.get('field_type', '')
        bbox = field.get('bbox', (0, 0, 0, 0))\n        \n        # Check field size (should be large enough for interaction)\n        if bbox and len(bbox) == 4:\n            width = abs(bbox[2] - bbox[0])\n            height = abs(bbox[3] - bbox[1])\n            \n            # Minimum sizes for different field types\n            min_sizes = {\n                'text': (80, 20),\n                'password': (80, 20),\n                'textarea': (100, 60),\n                'checkbox': (16, 16),\n                'radio': (16, 16),\n                'button': (60, 24),\n                'submit': (80, 28)\n            }\n            \n            min_width, min_height = min_sizes.get(field_type, (20, 20))\n            \n            if width < min_width or height < min_height:\n                issues.append({\n                    \"issue_type\": \"PDF23_field_too_small\",\n                    \"severity\": \"warning\",\n                    \"description\": f\"Form field may be too small for comfortable interaction ({width}x{height} px)\",\n                    \"suggestion\": f\"Consider increasing size to at least {min_width}x{min_height} px\"\n                })\n        \n        # Check for problematic field types\n        if field_type == 'unknown':\n            issues.append({\n                \"issue_type\": \"PDF23_unknown_field_type\",\n                \"severity\": \"critical\",\n                \"description\": \"Form field type cannot be determined\",\n                \"suggestion\": \"Ensure field has proper /FT (field type) entry\"\n            })\n        \n        return issues\n    \n    def _analyze_form_patterns(self, form_fields: List[Dict]) -> List[Dict]:\n        \"\"\"Analyze patterns across all form fields\"\"\"\n        issues = []\n        \n        if not form_fields:\n            return issues\n        \n        # Check for submit buttons (PDF15)\n        submit_buttons = [f for f in form_fields if f.get('field_type') in ['submit', 'button']]\n        if len(form_fields) > 1 and not submit_buttons:  # Forms with multiple fields need submit\n            issues.append({\n                \"issue_type\": \"PDF15_missing_submit_button\",\n                \"severity\": \"warning\",\n                \"description\": \"Form lacks submit button\",\n                \"suggestion\": \"Add submit button with submit-form action\",\n                \"pdf_technique\": \"PDF15\"\n            })\n        \n        # Check for tab order issues\n        pages_with_fields = {}\n        for field in form_fields:\n            page_num = field.get('page_num', 0)\n            if page_num not in pages_with_fields:\n                pages_with_fields[page_num] = []\n            pages_with_fields[page_num].append(field)\n        \n        for page_num, page_fields in pages_with_fields.items():\n            if len(page_fields) > 1:\n                # Sort fields by position (top to bottom, left to right)\n                sorted_fields = sorted(page_fields, key=lambda f: (-f.get('bbox', [0,0,0,0])[1], f.get('bbox', [0,0,0,0])[0]))\n                \n                # Check if field order makes sense\n                for i in range(len(sorted_fields) - 1):\n                    current_field = sorted_fields[i]\n                    next_field = sorted_fields[i + 1]\n                    \n                    # If fields are widely separated vertically, might indicate tab order issue\n                    current_y = current_field.get('bbox', [0,0,0,0])[1]\n                    next_y = next_field.get('bbox', [0,0,0,0])[1]\n                    \n                    if abs(current_y - next_y) > 100:  # Large vertical gap\n                        issues.append({\n                            \"issue_type\": \"PDF3_tab_order_issue\",\n                            \"severity\": \"info\",\n                            \"description\": f\"Field tab order may be confusing on page {page_num + 1}\",\n                            \"suggestion\": \"Review and adjust tab order for logical form completion\",\n                            \"pdf_technique\": \"PDF3\"\n                        })\n                        break  # Only report once per page\n        \n        return issues\n    \n    def _calculate_field_score(self, field: Dict, field_issues: List[Dict]) -> float:\n        \"\"\"Calculate accessibility score for individual field\"\"\"\n        if not field_issues:\n            return 100.0\n        \n        deductions = 0\n        for issue in field_issues:\n            severity = issue.get('severity', 'info')\n            if severity == 'critical':\n                deductions += 25\n            elif severity == 'warning':\n                deductions += 10\n            else:  # info\n                deductions += 5\n        \n        score = max(0, 100 - deductions)\n        return round(score, 1)\n    \n    def _calculate_form_accessibility_score(self) -> float:\n        \"\"\"Calculate overall form accessibility score\"\"\"\n        if not self.issues:\n            return 100.0\n        \n        total_deductions = 0\n        for issue in self.issues:\n            severity = issue.get('severity', 'info')\n            if severity == 'critical':\n                total_deductions += 15\n            elif severity == 'warning':\n                total_deductions += 8\n            else:  # info\n                total_deductions += 3\n        \n        score = max(0, 100 - total_deductions)\n        return round(score, 1)\n    \n    def _generate_form_recommendations(self, form_fields: List[Dict]) -> List[str]:\n        \"\"\"Generate actionable recommendations for form accessibility\"\"\"\n        recommendations = []\n        \n        if not form_fields:\n            return recommendations\n        \n        # Count issue types\n        issue_counts = {}\n        for issue in self.issues:\n            issue_type = issue.get('issue_type', 'unknown')\n            issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1\n        \n        # Generate specific recommendations\n        if issue_counts.get('PDF10_missing_label', 0) > 0:\n            recommendations.append(\n                f\"Add descriptive labels to {issue_counts['PDF10_missing_label']} form fields using /TU or /T entries\"\n            )\n        \n        if issue_counts.get('PDF12_missing_name', 0) > 0:\n            recommendations.append(\n                f\"Provide accessible names for {issue_counts['PDF12_missing_name']} form fields\"\n            )\n        \n        if issue_counts.get('PDF5_missing_required_indicator', 0) > 0:\n            recommendations.append(\n                f\"Add visual indicators for {issue_counts['PDF5_missing_required_indicator']} required fields\"\n            )\n        \n        if issue_counts.get('PDF15_missing_submit_button', 0) > 0:\n            recommendations.append(\"Add submit button with proper submit-form action\")\n        \n        if issue_counts.get('PDF23_field_too_small', 0) > 0:\n            recommendations.append(\n                f\"Increase size of {issue_counts['PDF23_field_too_small']} form fields for better usability\"\n            )\n        \n        # General recommendations\n        total_fields = len(form_fields)\n        critical_issues = len([i for i in self.issues if i.get('severity') == 'critical'])\n        \n        if critical_issues > total_fields * 0.3:  # More than 30% of fields have critical issues\n            recommendations.append(\"Consider comprehensive form accessibility review with assistive technology testing\")\n        \n        if len(form_fields) > 10:\n            recommendations.append(\"For large forms, consider grouping related fields and providing clear navigation\")\n        \n        return recommendations\n    \n    def get_pdf_technique_coverage(self) -> Dict[str, Dict]:\n        \"\"\"Get coverage of PDF techniques in form analysis\"\"\"\n        techniques_covered = {\n            \"PDF5\": {\n                \"title\": \"Indicating required form fields\",\n                \"implemented\": True,\n                \"checks\": [\"Required field indicators\", \"Visual cues for mandatory fields\"]\n            },\n            \"PDF10\": {\n                \"title\": \"Providing labels for interactive form controls\",\n                \"implemented\": True,\n                \"checks\": [\"Field labeling\", \"Descriptive labels\", \"Generic label detection\"]\n            },\n            \"PDF12\": {\n                \"title\": \"Providing name, role, value information for form fields\",\n                \"implemented\": True,\n                \"checks\": [\"Accessible name\", \"Field type (role)\", \"Value accessibility\"]\n            },\n            \"PDF15\": {\n                \"title\": \"Providing submit buttons with submit-form action\",\n                \"implemented\": True,\n                \"checks\": [\"Submit button presence\", \"Form submission functionality\"]\n            },\n            \"PDF22\": {\n                \"title\": \"Indicating when user input falls outside required format or values\",\n                \"implemented\": True,\n                \"checks\": [\"Field validation needs\", \"Error handling patterns\"]\n            },\n            \"PDF23\": {\n                \"title\": \"Providing interactive form controls\",\n                \"implemented\": True,\n                \"checks\": [\"Field sizing\", \"Interactive accessibility\", \"Field type validation\"]\n            }\n        }\n        \n        return techniques_covered