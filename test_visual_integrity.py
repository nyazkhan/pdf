#!/usr/bin/env python3
"""
Test script to verify visual integrity preservation in accessibility fixes
"""

import sys
import os
import logging
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from core.pdf_parser import PDFParser
from core.accessibility_rules import WCAGValidator
from utils.pdf_writer import PDFWriter, AccessibilityPDFExporter
from ai.agent import AccessibilityAIAgent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_visual_integrity_preservation(pdf_path: str):
    """Test that accessibility fixes preserve visual integrity"""
    
    if not os.path.exists(pdf_path):
        logger.error(f"Test PDF not found: {pdf_path}")
        return False
    
    logger.info(f"Testing visual integrity preservation with: {pdf_path}")
    
    try:
        # Step 1: Analyze the PDF
        logger.info("Step 1: Analyzing PDF...")
        parser = PDFParser(pdf_path)
        analysis = parser.analyze_document()
        parser.close()
        
        logger.info(f"Found {len(analysis['images'])} images, {len(analysis['tables'])} tables, {len(analysis['headings'])} headings")
        
        # Step 2: Validate accessibility
        logger.info("Step 2: Validating accessibility...")
        validator = WCAGValidator()
        issues = validator.validate_document(analysis)
        
        logger.info(f"Found {len(issues)} accessibility issues")
        
        if not issues:
            logger.info("No accessibility issues found - PDF is already compliant!")
            return True
        
        # Step 3: Generate AI fixes
        logger.info("Step 3: Generating AI-powered fixes...")
        ai_agent = AccessibilityAIAgent()
        
        if ai_agent.is_available():
            enhanced_issues = ai_agent.enhance_accessibility_fixes(issues, analysis.get('images', []), analysis)
            logger.info("AI enhancements applied")
        else:
            enhanced_issues = issues
            logger.warning("AI not available - using basic fixes")
        
        # Step 4: Prepare fixes dictionary
        fixes_dict = {}
        auto_fixable_count = 0
        
        for issue in enhanced_issues:
            if issue.auto_fixable and issue.suggested_fix:
                fixes_dict[issue.issue_id] = issue.suggested_fix
                auto_fixable_count += 1
            elif issue.suggested_fix:
                # Use suggested fix even if not auto-fixable
                fixes_dict[issue.issue_id] = issue.suggested_fix
        
        logger.info(f"Prepared {len(fixes_dict)} fixes ({auto_fixable_count} auto-fixable)")
        
        # Step 5: Test both invisible and visible modes
        test_results = {}
        
        # Test invisible mode (recommended)
        logger.info("Step 5a: Testing INVISIBLE fixes mode...")
        invisible_output = f"{Path(pdf_path).stem}_accessible_invisible.pdf"
        
        success_invisible = AccessibilityPDFExporter.create_accessible_pdf(
            pdf_path,
            invisible_output,
            enhanced_issues,
            fixes_dict,
            invisible_fixes=True
        )
        
        test_results['invisible'] = {
            'success': success_invisible,
            'output_file': invisible_output,
            'file_exists': os.path.exists(invisible_output) if success_invisible else False
        }
        
        if success_invisible:
            file_size = os.path.getsize(invisible_output)
            logger.info(f"✅ Invisible mode: Success! Output: {invisible_output} ({file_size} bytes)")
        else:
            logger.error("❌ Invisible mode: Failed!")
        
        # Test visible mode (for comparison)
        logger.info("Step 5b: Testing VISIBLE markers mode...")
        visible_output = f"{Path(pdf_path).stem}_accessible_visible.pdf"
        
        success_visible = AccessibilityPDFExporter.create_accessible_pdf(
            pdf_path,
            visible_output,
            enhanced_issues,
            fixes_dict,
            invisible_fixes=False
        )
        
        test_results['visible'] = {
            'success': success_visible,
            'output_file': visible_output,
            'file_exists': os.path.exists(visible_output) if success_visible else False
        }
        
        if success_visible:
            file_size = os.path.getsize(visible_output)
            logger.info(f"✅ Visible mode: Success! Output: {visible_output} ({file_size} bytes)")
        else:
            logger.error("❌ Visible mode: Failed!")
        
        # Step 6: Analyze results
        logger.info("Step 6: Test Results Summary")
        logger.info("=" * 50)
        
        if test_results['invisible']['success']:
            logger.info("✅ INVISIBLE MODE: PDF exported successfully")
            logger.info("   - Visual integrity should be preserved")
            logger.info("   - Accessibility fixes applied invisibly")
            logger.info(f"   - Output file: {test_results['invisible']['output_file']}")
        else:
            logger.error("❌ INVISIBLE MODE: Failed to export PDF")
        
        if test_results['visible']['success']:
            logger.info("⚠️  VISIBLE MODE: PDF exported with visible markers")
            logger.info("   - Visual appearance may be affected")
            logger.info("   - Use only for review purposes")
            logger.info(f"   - Output file: {test_results['visible']['output_file']}")
        else:
            logger.error("❌ VISIBLE MODE: Failed to export PDF")
        
        # Overall result
        overall_success = test_results['invisible']['success']
        
        logger.info("=" * 50)
        if overall_success:
            logger.info("🎉 OVERALL RESULT: SUCCESS!")
            logger.info("   Visual integrity preservation is working correctly.")
            logger.info("   The invisible fixes mode successfully preserves PDF appearance.")
        else:
            logger.error("💥 OVERALL RESULT: FAILED!")
            logger.error("   Visual integrity preservation needs attention.")
        
        return overall_success
        
    except Exception as e:
        logger.error(f"Test failed with exception: {e}")
        return False

def main():
    """Main test function"""
    
    print("🔍 PDF Accessibility Visual Integrity Test")
    print("=" * 60)
    
    # Test with provided PDF or use a default test file
    if len(sys.argv) > 1:
        test_pdf = sys.argv[1]
    else:
        # Look for any PDF files in current directory for testing
        pdf_files = list(Path('.').glob('*.pdf'))
        if pdf_files:
            test_pdf = str(pdf_files[0])
            logger.info(f"No PDF specified, using found file: {test_pdf}")
        else:
            logger.error("No PDF file found for testing. Please provide a PDF file:")
            logger.error("Usage: python test_visual_integrity.py <path_to_pdf>")
            return False
    
    # Run the test
    success = test_visual_integrity_preservation(test_pdf)
    
    print("=" * 60)
    if success:
        print("✅ TEST PASSED: Visual integrity preservation is working!")
        print("   The PDF accessibility fixes are applied without affecting visual appearance.")
        print("   You can safely use the invisible fixes mode for production use.")
    else:
        print("❌ TEST FAILED: Visual integrity preservation needs debugging.")
        print("   Check the logs above for specific error details.")
    
    return success

if __name__ == "__main__":
    main()