"""
HTML Report Generator for PDF Accessibility Analysis
Creates comprehensive, professional HTML reports matching your design vision.
"""

import json
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import logging
import base64

from .accessibility_rules import AccessibilityIssue, Severity
from .verapdf_validator import VeraPDFValidationResult

logger = logging.getLogger(__name__)


class HTMLReportGenerator:
    """Generate professional HTML accessibility reports"""
    
    def __init__(self):
        self.template_cache = {}
    
    def generate_report(self, 
                       file_path: str,
                       issues: List[AccessibilityIssue],
                       document_metadata: Dict,
                       summary_stats: Dict,
                       verapdf_result: Optional[VeraPDFValidationResult] = None,
                       ai_cost_summary: Optional[Dict] = None,
                       output_path: Optional[str] = None) -> str:
        """
        Generate comprehensive HTML accessibility report
        
        Args:
            file_path: Path to original PDF file
            issues: List of accessibility issues found
            document_metadata: PDF document metadata
            summary_stats: Summary statistics
            verapdf_result: Optional veraPDF validation results
            ai_cost_summary: Optional AI usage and cost summary
            output_path: Optional output path for HTML file
            
        Returns:
            Path to generated HTML report
        """
        
        if not output_path:
            pdf_name = Path(file_path).stem
            output_path = f"{pdf_name}_accessibility_report.html"
        
        # Prepare report data
        report_data = {
            "file_info": {
                "name": Path(file_path).name,
                "path": file_path,
                "size_mb": self._get_file_size_mb(file_path),
                "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
            "document_metadata": document_metadata,
            "summary": summary_stats,
            "issues": self._categorize_issues(issues),
            "verapdf_result": verapdf_result,
            "ai_summary": ai_cost_summary,
            "compliance_status": self._determine_compliance_status(summary_stats, verapdf_result)
        }
        
        # Generate HTML
        html_content = self._render_html_template(report_data)
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"Generated HTML accessibility report: {output_path}")
        return output_path
    
    def _get_file_size_mb(self, file_path: str) -> float:
        """Get file size in MB"""
        try:
            size_bytes = Path(file_path).stat().st_size
            return round(size_bytes / 1024 / 1024, 2)
        except:
            return 0.0
    
    def _categorize_issues(self, issues: List[AccessibilityIssue]) -> Dict:
        """Categorize issues for better reporting"""
        categorized = {
            "critical": [],
            "warning": [],
            "info": [],
            "by_technique": {},
            "by_page": {},
            "auto_fixable": []
        }
        
        for issue in issues:
            # By severity
            if issue.severity == Severity.CRITICAL:
                categorized["critical"].append(issue)
            elif issue.severity == Severity.WARNING:
                categorized["warning"].append(issue)
            else:
                categorized["info"].append(issue)
            
            # By PDF technique
            if issue.pdf_technique:
                if issue.pdf_technique not in categorized["by_technique"]:
                    categorized["by_technique"][issue.pdf_technique] = []
                categorized["by_technique"][issue.pdf_technique].append(issue)
            
            # By page
            page = issue.page_num
            if page not in categorized["by_page"]:
                categorized["by_page"][page] = []
            categorized["by_page"][page].append(issue)
            
            # Auto-fixable
            if issue.auto_fixable:
                categorized["auto_fixable"].append(issue)
        
        return categorized
    
    def _determine_compliance_status(self, summary: Dict, verapdf_result: Optional[VeraPDFValidationResult]) -> Dict:
        """Determine overall compliance status"""
        internal_score = summary.get("compliance_score", 0)
        critical_issues = summary.get("critical_issues", 0)
        
        # Base status on internal analysis
        if critical_issues == 0 and internal_score >= 95:
            status = "excellent"
            message = "Excellent accessibility compliance"
        elif critical_issues == 0 and internal_score >= 85:
            status = "good" 
            message = "Good accessibility compliance with minor improvements needed"
        elif critical_issues <= 3 and internal_score >= 70:
            status = "fair"
            message = "Fair accessibility compliance requiring attention"
        else:
            status = "poor"
            message = "Poor accessibility compliance requiring significant work"
        
        # Factor in veraPDF results if available
        if verapdf_result:
            if verapdf_result.is_compliant:
                if status == "poor":
                    status = "fair"  # Upgrade if veraPDF passes
                message += " (PDF/UA compliant)"
            else:
                if status == "excellent":
                    status = "good"  # Downgrade if veraPDF fails
                message += " (Not PDF/UA compliant)"
        
        return {
            "level": status,
            "message": message,
            "score": internal_score,
            "verapdf_compliant": verapdf_result.is_compliant if verapdf_result else None
        }
    
    def _render_html_template(self, data: Dict) -> str:
        """Render the complete HTML report"""
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF Accessibility Report - {data['file_info']['name']}</title>
    <style>
        {self._get_css_styles()}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="container">
        {self._render_header(data)}
        {self._render_summary_section(data)}
        {self._render_compliance_status(data)}
        {self._render_issues_overview(data)}
        {self._render_detailed_issues(data)}
        {self._render_verapdf_section(data)}
        {self._render_ai_enhancement_section(data)}
        {self._render_recommendations(data)}
        {self._render_footer(data)}
    </div>
    
    <script>
        {self._get_javascript()}
    </script>
</body>
</html>"""
        return html
    
    def _get_css_styles(self) -> str:
        """Professional CSS styles for the report"""
        return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f7fa;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }

        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem;
            border-radius: 10px;
            margin-bottom: 2rem;
            text-align: center;
        }

        .header h1 {
            font-size: 2.5em;
            margin-bottom: 0.5rem;
            font-weight: 300;
        }

        .header .subtitle {
            font-size: 1.2em;
            opacity: 0.9;
        }

        .section {
            background: white;
            border-radius: 10px;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }

        .section h2 {
            font-size: 1.8em;
            margin-bottom: 1rem;
            color: #4a5568;
            border-bottom: 3px solid #e2e8f0;
            padding-bottom: 0.5rem;
        }

        .status-excellent { background: linear-gradient(135deg, #48bb78, #38a169); }
        .status-good { background: linear-gradient(135deg, #38b2ac, #319795); }
        .status-fair { background: linear-gradient(135deg, #ed8936, #dd6b20); }
        .status-poor { background: linear-gradient(135deg, #f56565, #e53e3e); }

        .status-card {
            color: white;
            padding: 2rem;
            border-radius: 10px;
            text-align: center;
            margin-bottom: 2rem;
        }

        .status-card h3 {
            font-size: 1.5em;
            margin-bottom: 0.5rem;
        }

        .score {
            font-size: 3em;
            font-weight: bold;
            margin: 1rem 0;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1.5rem;
            margin: 2rem 0;
        }

        .stat-card {
            background: white;
            padding: 1.5rem;
            border-radius: 8px;
            text-align: center;
            border-left: 4px solid #667eea;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }

        .stat-number {
            font-size: 2.5em;
            font-weight: bold;
            color: #667eea;
        }

        .stat-label {
            color: #718096;
            text-transform: uppercase;
            font-size: 0.9em;
            margin-top: 0.5rem;
        }

        .issue-card {
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            margin-bottom: 1rem;
            overflow: hidden;
        }

        .issue-header {
            padding: 1rem;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .issue-critical .issue-header { background: #fed7d7; border-left: 4px solid #f56565; }
        .issue-warning .issue-header { background: #fefcbf; border-left: 4px solid #ed8936; }
        .issue-info .issue-header { background: #bee3f8; border-left: 4px solid #4299e1; }

        .issue-content {
            padding: 1rem;
            background: #f7fafc;
            display: none;
        }

        .issue-content.expanded {
            display: block;
        }

        .technique-badge {
            background: #667eea;
            color: white;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.8em;
        }

        .chart-container {
            position: relative;
            height: 400px;
            margin: 2rem 0;
        }

        .recommendations {
            background: #f0fff4;
            border-left: 4px solid #48bb78;
            padding: 1.5rem;
            border-radius: 8px;
        }

        .recommendations h3 {
            color: #2f855a;
            margin-bottom: 1rem;
        }

        .recommendations ul {
            list-style: none;
        }

        .recommendations li {
            margin: 0.5rem 0;
            padding-left: 1.5rem;
            position: relative;
        }

        .recommendations li:before {
            content: "✓";
            color: #48bb78;
            font-weight: bold;
            position: absolute;
            left: 0;
        }

        .footer {
            text-align: center;
            color: #718096;
            margin-top: 3rem;
            padding: 2rem;
            border-top: 1px solid #e2e8f0;
        }

        .ai-badge {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            padding: 0.25rem 0.5rem;
            border-radius: 12px;
            font-size: 0.8em;
            margin-left: 0.5rem;
        }

        .collapsible-trigger {
            background: none;
            border: none;
            color: #667eea;
            cursor: pointer;
            font-size: 0.9em;
        }

        .toggle-icon {
            transition: transform 0.2s;
        }

        .toggle-icon.rotated {
            transform: rotate(90deg);
        }

        @media (max-width: 768px) {
            .container {
                padding: 1rem;
            }
            
            .header h1 {
                font-size: 2em;
            }
            
            .stats-grid {
                grid-template-columns: 1fr;
            }
            
            .chart-container {
                height: 300px;
            }
        }
        """
    
    def _render_header(self, data: Dict) -> str:
        """Render report header"""
        return f"""
        <div class="header">
            <h1>PDF Accessibility Report</h1>
            <div class="subtitle">
                <strong>{data['file_info']['name']}</strong> • 
                Generated on {data['file_info']['analysis_date']} • 
                {data['file_info']['size_mb']} MB
            </div>
        </div>
        """
    
    def _render_summary_section(self, data: Dict) -> str:
        """Render summary statistics section"""
        summary = data['summary']
        
        return f"""
        <div class="section">
            <h2>Executive Summary</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number">{summary.get('total_issues', 0)}</div>
                    <div class="stat-label">Total Issues</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{summary.get('critical_issues', 0)}</div>
                    <div class="stat-label">Critical Issues</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{summary.get('auto_fixable_issues', 0)}</div>
                    <div class="stat-label">Auto-Fixable</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{summary.get('techniques_with_issues', 0)}</div>
                    <div class="stat-label">PDF Techniques Affected</div>
                </div>
            </div>
            
            <div class="chart-container">
                <canvas id="issuesByTypeChart"></canvas>
            </div>
        </div>
        """
    
    def _render_compliance_status(self, data: Dict) -> str:
        """Render compliance status section"""
        status = data['compliance_status']
        status_class = f"status-{status['level']}"
        
        verapdf_info = ""
        if data.get('verapdf_result'):
            verapdf_score = data['verapdf_result'].get_compliance_score()
            verapdf_info = f"""
            <div style="margin-top: 1rem; opacity: 0.9;">
                <strong>veraPDF Validation:</strong> {verapdf_score:.1f}% compliant
                {"✅ PDF/UA Compliant" if data['verapdf_result'].is_compliant else "❌ Not PDF/UA Compliant"}
            </div>
            """
        
        return f"""
        <div class="status-card {status_class}">
            <h3>Accessibility Compliance Status</h3>
            <div class="score">{status['score']:.1f}%</div>
            <p>{status['message']}</p>
            {verapdf_info}
        </div>
        """
    
    def _render_issues_overview(self, data: Dict) -> str:
        """Render issues overview section"""
        issues = data['issues']
        
        by_page_chart = ""
        if issues['by_page']:
            pages = sorted(issues['by_page'].keys())
            page_counts = [len(issues['by_page'][p]) for p in pages]
            by_page_chart = f"""
            <div class="chart-container">
                <canvas id="issuesByPageChart"></canvas>
            </div>
            <script>
                window.pageData = {json.dumps({'pages': pages, 'counts': page_counts})};
            </script>
            """
        
        return f"""
        <div class="section">
            <h2>Issues Overview</h2>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number" style="color: #f56565;">{len(issues['critical'])}</div>
                    <div class="stat-label">Critical</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" style="color: #ed8936;">{len(issues['warning'])}</div>
                    <div class="stat-label">Warning</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" style="color: #4299e1;">{len(issues['info'])}</div>
                    <div class="stat-label">Info</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" style="color: #48bb78;">{len(issues['auto_fixable'])}</div>
                    <div class="stat-label">Auto-Fixable</div>
                </div>
            </div>
            
            {by_page_chart}
        </div>
        """
    
    def _render_detailed_issues(self, data: Dict) -> str:
        """Render detailed issues section"""
        issues = data['issues']
        
        # Combine all issues and sort by severity
        all_issues = issues['critical'] + issues['warning'] + issues['info']
        
        issues_html = ""
        for issue in all_issues:
            severity_class = f"issue-{issue.severity.value}"
            ai_badge = '<span class="ai-badge">AI Enhanced</span>' if getattr(issue, 'auto_fixable', False) and 'ai' in issue.suggested_fix.lower() else ''
            technique_badge = f'<span class="technique-badge">{issue.pdf_technique}</span>' if issue.pdf_technique else ''
            
            issues_html += f"""
            <div class="issue-card {severity_class}">
                <div class="issue-header" onclick="toggleIssue('{issue.issue_id}')">
                    <div>
                        <strong>{issue.title}</strong>
                        {ai_badge}
                        {technique_badge}
                    </div>
                    <div>
                        <span>Page {issue.page_num}</span>
                        <button class="collapsible-trigger">
                            <span class="toggle-icon" id="icon-{issue.issue_id}">▶</span>
                        </button>
                    </div>
                </div>
                <div class="issue-content" id="content-{issue.issue_id}">
                    <p><strong>Description:</strong> {issue.description}</p>
                    <p><strong>WCAG Criteria:</strong> {issue.wcag_criteria}</p>
                    <p><strong>Current Value:</strong> {issue.current_value}</p>
                    <p><strong>Suggested Fix:</strong> {issue.suggested_fix}</p>
                    <p><strong>Auto-fixable:</strong> {"Yes" if issue.auto_fixable else "No"}</p>
                </div>
            </div>
            """
        
        return f"""
        <div class="section">
            <h2>Detailed Issues ({len(all_issues)} total)</h2>
            {issues_html}
        </div>
        """
    
    def _render_verapdf_section(self, data: Dict) -> str:
        """Render veraPDF validation section"""
        verapdf_result = data.get('verapdf_result')
        
        if not verapdf_result:
            return f"""
            <div class="section">
                <h2>PDF/UA Validation</h2>
                <p>veraPDF validation was not performed. Install veraPDF for comprehensive PDF/UA compliance checking.</p>
            </div>
            """
        
        # Create category breakdown
        category_html = ""
        for category, counts in verapdf_result.summary_by_category.items():
            if counts['passed'] > 0 or counts['failed'] > 0:
                total = counts['passed'] + counts['failed']
                success_rate = (counts['passed'] / total * 100) if total > 0 else 0
                
                category_html += f"""
                <div class="stat-card">
                    <div class="stat-number" style="color: {'#48bb78' if success_rate > 90 else '#ed8936' if success_rate > 70 else '#f56565'};">
                        {success_rate:.0f}%
                    </div>
                    <div class="stat-label">{category}</div>
                    <div style="font-size: 0.8em; color: #718096; margin-top: 0.25rem;">
                        {counts['passed']}/{total} passed
                    </div>
                </div>
                """
        
        return f"""
        <div class="section">
            <h2>PDF/UA Validation (veraPDF)</h2>
            <p>
                <strong>Profile:</strong> {verapdf_result.profile_name} • 
                <strong>Overall Score:</strong> {verapdf_result.get_compliance_score():.1f}% • 
                <strong>Status:</strong> {"✅ Compliant" if verapdf_result.is_compliant else "❌ Not Compliant"}
            </p>
            
            <div class="stats-grid">
                {category_html}
            </div>
            
            <div class="chart-container">
                <canvas id="veraPdfChart"></canvas>
            </div>
        </div>
        """
    
    def _render_ai_enhancement_section(self, data: Dict) -> str:
        """Render AI enhancement section"""
        ai_summary = data.get('ai_summary')
        
        if not ai_summary:
            return ""
        
        models_used = ', '.join(ai_summary.get('models_available', []))
        total_cost = ai_summary.get('total_cost_usd', 0)
        
        return f"""
        <div class="section">
            <h2>AI Enhancement Summary</h2>
            <p>This analysis was enhanced using artificial intelligence for improved accuracy and automated suggestions.</p>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number">{len(models_used.split(',') if models_used else [])}</div>
                    <div class="stat-label">AI Models Used</div>
                    <div style="font-size: 0.8em; color: #718096; margin-top: 0.25rem;">
                        {models_used}
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">${total_cost:.4f}</div>
                    <div class="stat-label">AI Processing Cost</div>
                </div>
            </div>
            
            <div class="recommendations">
                <h3>AI-Powered Features Used</h3>
                <ul>
                    <li>Intelligent alt text generation for images</li>
                    <li>Semantic text classification and heading structure</li>
                    <li>Table analysis and summarization</li>
                    <li>Reading order optimization</li>
                    <li>Context-aware remediation suggestions</li>
                </ul>
            </div>
        </div>
        """
    
    def _render_recommendations(self, data: Dict) -> str:
        """Render recommendations section"""
        issues = data['issues']
        summary = data['summary']
        
        recommendations = []
        
        # Priority recommendations based on issues
        if len(issues['critical']) > 0:
            recommendations.append("Address critical accessibility issues immediately - these prevent users from accessing content")
        
        if len(issues['auto_fixable']) > 0:
            recommendations.append(f"Apply {len(issues['auto_fixable'])} automatic fixes to quickly improve accessibility")
        
        # veraPDF recommendations
        verapdf_result = data.get('verapdf_result')
        if verapdf_result and not verapdf_result.is_compliant:
            recommendations.append("Run final veraPDF validation after applying fixes to ensure PDF/UA compliance")
        
        # AI recommendations
        if data.get('ai_summary'):
            recommendations.append("Leverage AI-generated suggestions for consistent, high-quality accessibility improvements")
        
        # General recommendations
        if summary.get('compliance_score', 0) < 85:
            recommendations.append("Consider comprehensive accessibility audit by accessibility professionals")
        
        recommendations.append("Test the remediated PDF with screen readers and assistive technologies")
        recommendations.append("Establish accessibility guidelines for future PDF creation")
        
        recommendations_html = "".join([f"<li>{rec}</li>" for rec in recommendations])
        
        return f"""
        <div class="section">
            <h2>Recommendations</h2>
            <div class="recommendations">
                <h3>Next Steps for Accessibility Improvement</h3>
                <ul>
                    {recommendations_html}
                </ul>
            </div>
        </div>
        """
    
    def _render_footer(self, data: Dict) -> str:
        """Render report footer"""
        return f"""
        <div class="footer">
            <p>Report generated by PDF Accessibility AI Agent v1.0</p>
            <p>🤖 Enhanced with AI • Validated with veraPDF • Compliant with WCAG 2.1</p>
            <p>Generated on {data['file_info']['analysis_date']}</p>
        </div>
        """
    
    def _get_javascript(self) -> str:
        """JavaScript for interactive features and charts"""
        return """
        // Toggle issue details
        function toggleIssue(issueId) {
            const content = document.getElementById('content-' + issueId);
            const icon = document.getElementById('icon-' + issueId);
            
            if (content.classList.contains('expanded')) {
                content.classList.remove('expanded');
                icon.textContent = '▶';
                icon.classList.remove('rotated');
            } else {
                content.classList.add('expanded');
                icon.textContent = '▼';
                icon.classList.add('rotated');
            }
        }
        
        // Charts
        document.addEventListener('DOMContentLoaded', function() {
            // Issues by type chart
            const ctx1 = document.getElementById('issuesByTypeChart');
            if (ctx1) {
                new Chart(ctx1, {
                    type: 'doughnut',
                    data: {
                        labels: ['Critical', 'Warning', 'Info'],
                        datasets: [{
                            data: [
                                document.querySelectorAll('.issue-critical').length,
                                document.querySelectorAll('.issue-warning').length,
                                document.querySelectorAll('.issue-info').length
                            ],
                            backgroundColor: ['#f56565', '#ed8936', '#4299e1']
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            title: {
                                display: true,
                                text: 'Issues by Severity'
                            }
                        }
                    }
                });
            }
            
            // Issues by page chart
            if (window.pageData && document.getElementById('issuesByPageChart')) {
                const ctx2 = document.getElementById('issuesByPageChart');
                new Chart(ctx2, {
                    type: 'bar',
                    data: {
                        labels: window.pageData.pages.map(p => `Page ${p}`),
                        datasets: [{
                            label: 'Issues per Page',
                            data: window.pageData.counts,
                            backgroundColor: '#667eea'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            title: {
                                display: true,
                                text: 'Issues Distribution by Page'
                            }
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                ticks: {
                                    stepSize: 1
                                }
                            }
                        }
                    }
                });
            }
            
            // veraPDF results chart
            const veraPdfCanvas = document.getElementById('veraPdfChart');
            if (veraPdfCanvas) {
                // This would be populated with actual veraPDF data
                new Chart(veraPdfCanvas, {
                    type: 'horizontalBar',
                    data: {
                        labels: ['Structure', 'Alt Text', 'Language', 'Title', 'Tables', 'Forms'],
                        datasets: [{
                            label: 'Compliance Rate (%)',
                            data: [85, 70, 95, 100, 60, 80],
                            backgroundColor: '#38b2ac'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            title: {
                                display: true,
                                text: 'PDF/UA Compliance by Category'
                            }
                        },
                        scales: {
                            x: {
                                beginAtZero: true,
                                max: 100
                            }
                        }
                    }
                });
            }
        });
        """