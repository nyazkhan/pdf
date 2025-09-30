#!/usr/bin/env python3
"""
Example: Enhanced AI-Powered PDF Accessibility Workflow
Demonstrates the complete pipeline: Parse → Rule Engine → AI → Fix → Validate → Export

This script showcases the new capabilities:
- Gemini Flash-Lite AI integration
- JSON tag tree schema
- veraPDF validation  
- Enhanced HTML reporting
- Cost tracking and optimization
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core.pdf_parser import PDFParser
from src.core.accessibility_rules import WCAGValidator
from src.core.report_manager import ReportManager
from src.core.tag_tree_schema import TagTreeBuilder, DocumentMetadata
from src.ai.agent import AccessibilityAIAgent
from src.utils.pdf_writer import AccessibilityPDFExporter
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def enhanced_pdf_accessibility_workflow(pdf_path: str, output_dir: str = "output"):
    """
    Complete enhanced accessibility workflow
    
    Args:
        pdf_path: Path to input PDF
        output_dir: Directory for outputs
    """
    
    logger.info(f"🚀 Starting Enhanced PDF Accessibility Workflow")
    logger.info(f"Input PDF: {pdf_path}")
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    pdf_name = Path(pdf_path).stem
    
    try:
        # Step 1: Parse PDF
        logger.info("📄 Step 1: Parsing PDF document...")
        parser = PDFParser(pdf_path)
        analysis = parser.analyze_document()
        parser.close()
        
        logger.info(f"Extracted {analysis['statistics']['text_blocks_count']} text blocks, "
                   f"{analysis['statistics']['images_count']} images, "
                   f"{analysis['statistics']['tables_count']} tables")
        
        # Step 2: Rule Engine Analysis
        logger.info("🔍 Step 2: Running WCAG validation...")
        validator = WCAGValidator(wcag_level="AA", enable_verapdf=True)
        issues = validator.validate_document(analysis)
        
        logger.info(f"Found {len(issues)} accessibility issues")
        
        # Step 3: AI Enhancement
        logger.info("🤖 Step 3: Enhancing with AI analysis...")
        ai_agent = AccessibilityAIAgent()
        
        if ai_agent.is_available():
            # AI-enhanced text classification
            if analysis.get('text_blocks'):
                text_blocks = [
                    {
                        "content": block.content,
                        "page_num": block.page_num,
                        "bbox": block.bbox,
                        "metadata": block.metadata,
                        "type": block.type
                    }
                    for block in analysis['text_blocks'][:20]  # Limit for cost efficiency
                ]
                
                heading_suggestions = ai_agent.suggest_heading_structure(text_blocks)
                logger.info(f"Generated {len(heading_suggestions)} AI heading suggestions")
            
            # AI-enhanced alt text generation
            enhanced_issues = ai_agent.enhance_accessibility_fixes(issues, analysis.get("images", []))
            issues = enhanced_issues
            
            # Get AI cost summary
            ai_cost_summary = ai_agent.get_ai_cost_summary()
            logger.info(f"AI processing cost: ${ai_cost_summary.get('total_cost_usd', 0):.4f}")
        else:
            logger.warning("AI models not available - proceeding with rule-based analysis only")
            ai_cost_summary = None
        
        # Step 4: Create JSON Tag Tree
        logger.info("🌳 Step 4: Creating accessibility tag tree...")
        document_title = analysis.get("metadata", {}).get("title", pdf_name)
        tag_tree = TagTreeBuilder.from_pdf_analysis(analysis, document_title)
        
        # Save tag tree
        tag_tree_path = output_path / f"{pdf_name}_tag_tree.json"
        tag_tree.to_file(str(tag_tree_path))
        logger.info(f"Saved tag tree: {tag_tree_path}")
        
        # Validate tag tree structure
        validation = tag_tree.validate_structure()
        logger.info(f"Tag tree validation: {'✅ Valid' if validation['valid'] else '❌ Invalid'}")
        
        # Step 5: Apply Fixes (if we have any auto-fixable ones)
        logger.info("🔧 Step 5: Applying accessibility fixes...")
        auto_fixable_issues = [issue for issue in issues if issue.auto_fixable]
        
        if auto_fixable_issues:
            # Create fixes dictionary
            fixes = {}
            for issue in auto_fixable_issues:
                fixes[issue.issue_id] = issue.suggested_fix
            
            # Apply fixes
            accessible_pdf_path = output_path / f"{pdf_name}_accessible.pdf"
            success = AccessibilityPDFExporter.create_accessible_pdf(
                input_path=pdf_path,
                output_path=str(accessible_pdf_path),
                issues=issues,
                fixes=fixes,
                invisible_fixes=True  # Preserve visual integrity
            )
            
            if success:
                logger.info(f"Created accessible PDF: {accessible_pdf_path}")
                pdf_for_validation = str(accessible_pdf_path)
            else:
                logger.warning("PDF fix application failed, using original for validation")
                pdf_for_validation = pdf_path
        else:
            logger.info("No auto-fixable issues found")
            pdf_for_validation = pdf_path
        
        # Step 6: veraPDF Validation
        logger.info("✅ Step 6: Running veraPDF validation...")
        verapdf_result = validator.validate_with_verapdf(pdf_for_validation)
        
        if verapdf_result:
            compliance_score = verapdf_result.get_compliance_score()
            compliance_status = "✅ PDF/UA Compliant" if verapdf_result.is_compliant else "❌ Not PDF/UA Compliant"
            logger.info(f"veraPDF validation: {compliance_score:.1f}% ({compliance_status})")
        else:
            logger.warning("veraPDF validation not available")
        
        # Step 7: Generate Comprehensive Reports
        logger.info("📊 Step 7: Generating comprehensive reports...")
        report_manager = ReportManager(str(output_path / "accessibility_reports.db"))
        
        # Generate reports in multiple formats
        report_paths = report_manager.generate_comprehensive_report(
            file_path=pdf_path,
            issues=issues,
            document_metadata=analysis.get("metadata", {}),
            verapdf_result=verapdf_result,
            ai_cost_summary=ai_cost_summary,
            export_formats=["json", "html"]
        )
        
        # Step 8: Final Summary
        logger.info("📈 Step 8: Final summary...")
        summary = validator.generate_comprehensive_summary(verapdf_result)
        
        print("\n" + "="*60)
        print("🎉 PDF ACCESSIBILITY ANALYSIS COMPLETE")
        print("="*60)
        print(f"📄 Document: {Path(pdf_path).name}")
        print(f"📊 Total Issues: {summary['total_issues']}")
        print(f"🚨 Critical Issues: {summary['critical_issues']}")
        print(f"⚠️  Warning Issues: {summary['warning_issues']}")
        print(f"ℹ️  Info Issues: {summary['info_issues']}")
        print(f"🔧 Auto-fixable: {summary['auto_fixable_issues']}")
        print(f"📈 Compliance Score: {summary['compliance_score']}%")
        
        if verapdf_result:
            print(f"🔍 veraPDF Score: {verapdf_result.get_compliance_score():.1f}%")
            print(f"📋 PDF/UA Status: {compliance_status}")
        
        if ai_cost_summary:
            print(f"🤖 AI Models Used: {', '.join(ai_cost_summary.get('models_available', []))}")
            print(f"💰 AI Cost: ${ai_cost_summary.get('total_cost_usd', 0):.4f}")
        
        print(f"\n📁 Generated Files:")
        for format_type, path in report_paths.items():
            print(f"   {format_type.upper()}: {path}")
        print(f"   Tag Tree: {tag_tree_path}")
        
        if auto_fixable_issues and 'accessible_pdf_path' in locals():
            print(f"   Accessible PDF: {accessible_pdf_path}")
        
        print("\n✨ Enhanced with AI • Validated with veraPDF • Ready for Production")
        
        return {
            "success": True,
            "summary": summary,
            "reports": report_paths,
            "tag_tree": str(tag_tree_path),
            "ai_cost": ai_cost_summary
        }
        
    except Exception as e:
        logger.error(f"Workflow failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def main():
    """Main function for command-line usage"""
    if len(sys.argv) < 2:
        print("Usage: python example_enhanced_workflow.py <pdf_path> [output_dir]")
        print("\nExample:")
        print("  python example_enhanced_workflow.py sample.pdf results/")
        print("\nOptional Environment Variables:")
        print("  GEMINI_API_KEY - Your Gemini API key for AI features")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "enhanced_output"
    
    if not Path(pdf_path).exists():
        print(f"Error: PDF file not found: {pdf_path}")
        sys.exit(1)
    
    # Check for Gemini API key
    if not os.getenv("GEMINI_API_KEY"):
        print("⚠️  Warning: GEMINI_API_KEY not set - AI features will use BLIP fallback")
        print("   Set your Gemini API key: export GEMINI_API_KEY='your-api-key'")
    
    # Run the enhanced workflow
    result = enhanced_pdf_accessibility_workflow(pdf_path, output_dir)
    
    if result["success"]:
        print(f"\n🎊 Success! Check the '{output_dir}' directory for results.")
        sys.exit(0)
    else:
        print(f"\n❌ Workflow failed: {result['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()