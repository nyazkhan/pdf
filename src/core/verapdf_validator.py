"""
veraPDF Integration for PDF/UA Compliance Validation
Provides wrapper for veraPDF command-line tool to validate PDF accessibility compliance.
"""

import subprocess
import logging
import json
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
import tempfile
import os

logger = logging.getLogger(__name__)


@dataclass
class VeraPDFRule:
    """Individual veraPDF validation rule result"""
    rule_id: str
    object_type: str
    test_number: int
    status: str  # "passed", "failed"
    message: str
    location: Optional[str] = None
    page_number: Optional[int] = None


@dataclass
class VeraPDFValidationResult:
    """Complete veraPDF validation result"""
    is_compliant: bool
    profile_name: str
    total_checks: int
    passed_checks: int
    failed_checks: int
    
    # Detailed results
    passed_rules: List[VeraPDFRule]
    failed_rules: List[VeraPDFRule]
    
    # Summary by category
    summary_by_category: Dict[str, Dict[str, int]]
    
    # PDF/UA specific info
    pdf_ua_version: str = "PDF/UA-1"
    validation_date: Optional[str] = None
    file_size: Optional[int] = None
    
    def get_compliance_score(self) -> float:
        """Calculate compliance score as percentage"""
        if self.total_checks == 0:
            return 100.0
        return (self.passed_checks / self.total_checks) * 100.0
    
    def get_critical_failures(self) -> List[VeraPDFRule]:
        """Get most critical validation failures"""
        # Priority order for PDF/UA rules
        critical_categories = [
            "Structure", "Tagged content", "Alternative descriptions",
            "Language", "Title", "Bookmarks", "Reading order"
        ]
        
        critical_failures = []
        for category in critical_categories:
            for rule in self.failed_rules:
                if any(cat.lower() in rule.message.lower() for cat in [category.lower()]):
                    critical_failures.append(rule)
        
        return critical_failures[:10]  # Top 10 most critical


class VeraPDFValidator:
    """Wrapper for veraPDF command-line validation"""
    
    def __init__(self, verapdf_path: Optional[str] = None):
        self.verapdf_path = verapdf_path or self._find_verapdf()
        self.available = self._check_availability()
        
        if self.available:
            logger.info(f"veraPDF found at: {self.verapdf_path}")
        else:
            logger.warning("veraPDF not available - PDF/UA validation will be limited")
    
    def _find_verapdf(self) -> Optional[str]:
        """Try to find veraPDF installation"""
        possible_paths = [
            # Common installation paths
            "/Applications/veraPDF-installer/verapdf",
            "/usr/local/bin/verapdf",
            "/opt/verapdf/verapdf",
            "verapdf",  # In PATH
            
            # Windows paths
            "C:\\Program Files\\veraPDF\\verapdf.exe",
            "C:\\Program Files (x86)\\veraPDF\\verapdf.exe",
            
            # Docker/container paths
            "/usr/bin/verapdf"
        ]
        
        for path in possible_paths:
            if Path(path).exists() or self._test_command(path):
                return path
        
        return None
    
    def _test_command(self, command: str) -> bool:
        """Test if command is available"""
        try:
            result = subprocess.run(
                [command, "--version"],
                capture_output=True,
                timeout=10
            )
            return result.returncode == 0
        except:
            return False
    
    def _check_availability(self) -> bool:
        """Check if veraPDF is available and working"""
        if not self.verapdf_path:
            return False
        
        try:
            result = subprocess.run(
                [self.verapdf_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                version_info = result.stdout.strip()
                logger.info(f"veraPDF version: {version_info}")
                return True
                
        except Exception as e:
            logger.debug(f"veraPDF availability check failed: {e}")
        
        return False
    
    def is_available(self) -> bool:
        """Check if validator is available"""
        return self.available
    
    def validate_pdf_ua(self, pdf_path: str, output_format: str = "xml") -> Optional[VeraPDFValidationResult]:
        """
        Validate PDF against PDF/UA standard
        
        Args:
            pdf_path: Path to PDF file to validate
            output_format: Output format ("xml", "json", "text")
            
        Returns:
            VeraPDFValidationResult or None if validation failed
        """
        if not self.is_available():
            logger.error("veraPDF is not available")
            return None
        
        if not Path(pdf_path).exists():
            logger.error(f"PDF file not found: {pdf_path}")
            return None
        
        try:
            logger.info(f"Validating PDF/UA compliance: {pdf_path}")
            
            # Create temporary output file
            with tempfile.NamedTemporaryFile(mode='w', suffix=f'.{output_format}', delete=False) as temp_file:
                output_path = temp_file.name
            
            try:
                # Build veraPDF command
                cmd = [
                    self.verapdf_path,
                    "--flavour", "ua1",  # PDF/UA-1 profile
                    "--format", output_format,
                    "--output", output_path,
                    pdf_path
                ]
                
                # Run veraPDF validation
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )
                
                if result.returncode != 0:
                    logger.error(f"veraPDF validation failed: {result.stderr}")
                    return None
                
                # Parse results based on format
                if output_format == "xml":
                    return self._parse_xml_results(output_path, pdf_path)
                elif output_format == "json":
                    return self._parse_json_results(output_path, pdf_path)
                else:
                    logger.error(f"Unsupported output format: {output_format}")
                    return None
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(output_path)
                except:
                    pass
                
        except subprocess.TimeoutExpired:
            logger.error("veraPDF validation timed out")
            return None
        except Exception as e:
            logger.error(f"veraPDF validation error: {e}")
            return None
    
    def _parse_xml_results(self, xml_path: str, pdf_path: str) -> Optional[VeraPDFValidationResult]:
        """Parse XML output from veraPDF"""
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            # Extract validation info
            validation_info = root.find(".//validationInfo")
            if validation_info is None:
                logger.error("No validation info found in veraPDF XML")
                return None
            
            profile_name = validation_info.get("profile", "PDF/UA-1")
            is_compliant = validation_info.get("compliant", "false").lower() == "true"
            
            # Count checks
            total_checks = 0
            passed_checks = 0
            failed_checks = 0
            
            passed_rules = []
            failed_rules = []
            
            # Parse test assertions
            for assertion in root.findall(".//assertion"):
                total_checks += 1
                
                rule_id = assertion.get("id", "unknown")
                object_type = assertion.get("objectType", "unknown")
                test_number = int(assertion.get("testNumber", 0))
                status = assertion.get("status", "unknown")
                
                # Get message
                message_elem = assertion.find("message")
                message = message_elem.text if message_elem is not None else ""
                
                # Get location if available
                location_elem = assertion.find("location")
                location = location_elem.text if location_elem is not None else None
                
                # Create rule object
                rule = VeraPDFRule(
                    rule_id=rule_id,
                    object_type=object_type,
                    test_number=test_number,
                    status=status,
                    message=message,
                    location=location
                )
                
                if status == "passed":
                    passed_checks += 1
                    passed_rules.append(rule)
                else:
                    failed_checks += 1
                    failed_rules.append(rule)
            
            # Create summary by category
            summary_by_category = self._categorize_rules(passed_rules + failed_rules)
            
            # Get file info
            file_size = Path(pdf_path).stat().st_size if Path(pdf_path).exists() else None
            
            result = VeraPDFValidationResult(
                is_compliant=is_compliant,
                profile_name=profile_name,
                total_checks=total_checks,
                passed_checks=passed_checks,
                failed_checks=failed_checks,
                passed_rules=passed_rules,
                failed_rules=failed_rules,
                summary_by_category=summary_by_category,
                file_size=file_size
            )
            
            logger.info(f"veraPDF validation complete: {passed_checks}/{total_checks} passed ({result.get_compliance_score():.1f}%)")
            return result
            
        except ET.ParseError as e:
            logger.error(f"Failed to parse veraPDF XML output: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing veraPDF results: {e}")
            return None
    
    def _parse_json_results(self, json_path: str, pdf_path: str) -> Optional[VeraPDFValidationResult]:
        """Parse JSON output from veraPDF"""
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
            
            # Extract validation results
            report = data.get("report", {})
            validation_result = report.get("validationResult", {})
            
            is_compliant = validation_result.get("compliant", False)
            profile_name = validation_result.get("profile", "PDF/UA-1")
            
            # Process test assertions
            passed_rules = []
            failed_rules = []
            
            for assertion in validation_result.get("testAssertions", []):
                rule = VeraPDFRule(
                    rule_id=assertion.get("ruleId", "unknown"),
                    object_type=assertion.get("objectType", "unknown"),
                    test_number=assertion.get("testNumber", 0),
                    status=assertion.get("status", "unknown"),
                    message=assertion.get("message", "")
                )
                
                if rule.status == "passed":
                    passed_rules.append(rule)
                else:
                    failed_rules.append(rule)
            
            total_checks = len(passed_rules) + len(failed_rules)
            summary_by_category = self._categorize_rules(passed_rules + failed_rules)
            file_size = Path(pdf_path).stat().st_size if Path(pdf_path).exists() else None
            
            result = VeraPDFValidationResult(
                is_compliant=is_compliant,
                profile_name=profile_name,
                total_checks=total_checks,
                passed_checks=len(passed_rules),
                failed_checks=len(failed_rules),
                passed_rules=passed_rules,
                failed_rules=failed_rules,
                summary_by_category=summary_by_category,
                file_size=file_size
            )
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse veraPDF JSON output: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing veraPDF JSON results: {e}")
            return None
    
    def _categorize_rules(self, rules: List[VeraPDFRule]) -> Dict[str, Dict[str, int]]:
        """Categorize rules by type for summary"""
        categories = {
            "Structure": {"passed": 0, "failed": 0},
            "Tagged Content": {"passed": 0, "failed": 0},
            "Alternative Text": {"passed": 0, "failed": 0},
            "Language": {"passed": 0, "failed": 0},
            "Title": {"passed": 0, "failed": 0},
            "Bookmarks": {"passed": 0, "failed": 0},
            "Reading Order": {"passed": 0, "failed": 0},
            "Forms": {"passed": 0, "failed": 0},
            "Tables": {"passed": 0, "failed": 0},
            "Lists": {"passed": 0, "failed": 0},
            "Other": {"passed": 0, "failed": 0}
        }
        
        # Categorization mapping
        category_keywords = {
            "Structure": ["struct", "tag", "element"],
            "Tagged Content": ["content", "marked", "artifact"],
            "Alternative Text": ["alt", "alternative", "description"],
            "Language": ["lang", "language"],
            "Title": ["title", "metadata"],
            "Bookmarks": ["bookmark", "outline"],
            "Reading Order": ["order", "sequence"],
            "Forms": ["form", "field", "widget"],
            "Tables": ["table", "row", "cell"],
            "Lists": ["list", "item"]
        }
        
        for rule in rules:
            categorized = False
            rule_text = (rule.message + " " + rule.object_type).lower()
            
            for category, keywords in category_keywords.items():
                if any(keyword in rule_text for keyword in keywords):
                    if rule.status == "passed":
                        categories[category]["passed"] += 1
                    else:
                        categories[category]["failed"] += 1
                    categorized = True
                    break
            
            if not categorized:
                if rule.status == "passed":
                    categories["Other"]["passed"] += 1
                else:
                    categories["Other"]["failed"] += 1
        
        return categories
    
    def validate_multiple_pdfs(self, pdf_paths: List[str]) -> Dict[str, Optional[VeraPDFValidationResult]]:
        """Validate multiple PDFs and return results"""
        results = {}
        
        for pdf_path in pdf_paths:
            try:
                logger.info(f"Validating PDF {pdf_path}")
                result = self.validate_pdf_ua(pdf_path)
                results[pdf_path] = result
                
                if result:
                    logger.info(f"PDF {Path(pdf_path).name}: {result.get_compliance_score():.1f}% compliant")
                else:
                    logger.warning(f"PDF {Path(pdf_path).name}: validation failed")
                    
            except Exception as e:
                logger.error(f"Error validating {pdf_path}: {e}")
                results[pdf_path] = None
        
        return results
    
    def generate_compliance_report(self, result: VeraPDFValidationResult, pdf_path: str) -> Dict:
        """Generate comprehensive compliance report"""
        report = {
            "file_info": {
                "path": pdf_path,
                "name": Path(pdf_path).name,
                "size_bytes": result.file_size,
                "size_mb": round(result.file_size / 1024 / 1024, 2) if result.file_size else None
            },
            "validation_summary": {
                "is_compliant": result.is_compliant,
                "compliance_score": result.get_compliance_score(),
                "profile": result.profile_name,
                "total_checks": result.total_checks,
                "passed_checks": result.passed_checks,
                "failed_checks": result.failed_checks
            },
            "category_breakdown": result.summary_by_category,
            "critical_issues": [
                {
                    "rule_id": rule.rule_id,
                    "message": rule.message,
                    "object_type": rule.object_type,
                    "location": rule.location
                }
                for rule in result.get_critical_failures()
            ],
            "recommendations": self._generate_recommendations(result)
        }
        
        return report
    
    def _generate_recommendations(self, result: VeraPDFValidationResult) -> List[str]:
        """Generate remediation recommendations"""
        recommendations = []
        
        if not result.is_compliant:
            recommendations.append("Document is not PDF/UA compliant and requires accessibility improvements.")
        
        # Analyze failed rules for specific recommendations
        failed_categories = {cat: data["failed"] for cat, data in result.summary_by_category.items() if data["failed"] > 0}
        
        if failed_categories.get("Alternative Text", 0) > 0:
            recommendations.append("Add alternative text descriptions for images and figures.")
        
        if failed_categories.get("Structure", 0) > 0:
            recommendations.append("Improve document structure with proper headings and tags.")
        
        if failed_categories.get("Language", 0) > 0:
            recommendations.append("Specify document language in PDF metadata.")
        
        if failed_categories.get("Title", 0) > 0:
            recommendations.append("Add descriptive title to document metadata.")
        
        if failed_categories.get("Tables", 0) > 0:
            recommendations.append("Ensure tables have proper headers and structure.")
        
        if failed_categories.get("Forms", 0) > 0:
            recommendations.append("Add labels and descriptions to form fields.")
        
        if failed_categories.get("Reading Order", 0) > 0:
            recommendations.append("Verify and correct logical reading order.")
        
        # General recommendations based on compliance score
        score = result.get_compliance_score()
        if score < 50:
            recommendations.append("Document requires comprehensive accessibility remediation.")
        elif score < 80:
            recommendations.append("Document has moderate accessibility issues that should be addressed.")
        elif score < 95:
            recommendations.append("Document is mostly accessible with minor issues to resolve.")
        
        return recommendations


def install_verapdf_instructions() -> str:
    """Return installation instructions for veraPDF"""
    return """
veraPDF Installation Instructions:

1. Download veraPDF from: https://verapdf.org/software/

2. Installation options:
   
   macOS:
   - Download the installer and run it
   - Or use Homebrew: brew install --cask verapdf
   
   Linux:
   - Download the installer script
   - Run: chmod +x verapdf-installer.sh && ./verapdf-installer.sh
   
   Windows:
   - Download the Windows installer
   - Run the installer and follow prompts
   
   Docker:
   - Use the official image: docker pull verapdf/verapdf

3. Verify installation:
   - Run: verapdf --version
   - Should show version information

4. For automated use, ensure verapdf is in your PATH or specify the full path in configuration.
"""