import logging
from typing import List, Dict, Optional, Tuple
import yaml
from pathlib import Path
import io
from PIL import Image

from .alt_text_generator import AltTextGenerator
from .gemini_client import GeminiClient
from ..core.accessibility_rules import AccessibilityIssue
# from ..core.form_analyzer import FormAnalyzer  # Temporarily disabled due to syntax issue

logger = logging.getLogger(__name__)


class AccessibilityAIAgent:
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self.load_config(config_path)
        self.alt_text_generator = None
        self.gemini_client = None
        self.initialized = False
        self.ai_mode = "hybrid"  # "blip", "gemini", or "hybrid"
        
        # Initialize models
        self.initialize_models()
    
    def load_config(self, config_path: str) -> Dict:
        try:
            if Path(config_path).exists():
                with open(config_path, 'r') as f:
                    return yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"Failed to load config: {e}")
        
        # Default configuration
        return {
            "ai_models": {
                "vision_model": "Salesforce/blip-image-captioning-base",
                "device": "cpu",
                "gemini_model": "gemini-2.0-flash-exp",
                "use_gemini": True,
                "gemini_api_key": None,
                "ai_mode": "hybrid"  # "blip", "gemini", or "hybrid"
            }
        }
    
    def initialize_models(self):
        try:
            model_config = self.config.get("ai_models", {})
            vision_model = model_config.get("vision_model", "Salesforce/blip-image-captioning-base")
            device = model_config.get("device", "cpu")
            use_gemini = model_config.get("use_gemini", True)
            gemini_model = model_config.get("gemini_model", "gemini-2.0-flash-exp")
            gemini_api_key = model_config.get("gemini_api_key")
            self.ai_mode = model_config.get("ai_mode", "hybrid")
            
            logger.info(f"Initializing AI models - Mode: {self.ai_mode}")
            
            # Initialize BLIP model (fallback and for specific tasks)
            if self.ai_mode in ["blip", "hybrid"]:
                logger.info(f"Initializing BLIP vision model: {vision_model}")
                self.alt_text_generator = AltTextGenerator(
                    model_name=vision_model,
                    device=device
                )
            
            # Initialize Gemini client
            if self.ai_mode in ["gemini", "hybrid"] and use_gemini:
                logger.info(f"Initializing Gemini model: {gemini_model}")
                self.gemini_client = GeminiClient(
                    api_key=gemini_api_key,
                    model_name=gemini_model
                )
                
                if not self.gemini_client.is_available():
                    logger.warning("Gemini client initialization failed - falling back to BLIP-only mode")
                    self.ai_mode = "blip"
            
            # Check if any model is available
            blip_available = self.alt_text_generator and self.alt_text_generator.is_available() if self.alt_text_generator else False
            gemini_available = self.gemini_client and self.gemini_client.is_available() if self.gemini_client else False
            
            self.initialized = blip_available or gemini_available
            
            if self.initialized:
                available_models = []
                if blip_available:
                    available_models.append("BLIP")
                if gemini_available:
                    available_models.append("Gemini")
                logger.info(f"AI models initialized successfully: {', '.join(available_models)}")
            else:
                logger.error("No AI models could be initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize AI models: {e}")
            self.initialized = False
    
    def is_available(self) -> bool:
        return self.initialized and (
            (self.alt_text_generator and self.alt_text_generator.is_available()) or
            (self.gemini_client and self.gemini_client.is_available())
        )
    
    def generate_alt_text(self, image_data: bytes, context: str = "") -> str:
        if not self.is_available():
            logger.warning("AI models not available")
            return "AI models not available"
        
        try:
            # Prefer Gemini for alt text generation if available
            if self.gemini_client and self.gemini_client.is_available() and self.ai_mode in ["gemini", "hybrid"]:
                logger.info("Generating alt text with Gemini")
                alt_text = self.gemini_client.generate_alt_text(image_data, context)
                
                # If Gemini fails and we have BLIP as fallback
                if alt_text.startswith("Error") and self.alt_text_generator and self.ai_mode == "hybrid":
                    logger.warning("Gemini failed, falling back to BLIP")
                    image = Image.open(io.BytesIO(image_data))
                    alt_text = self.alt_text_generator.generate_caption(image, context)
                
                return alt_text
                
            # Fallback to BLIP
            elif self.alt_text_generator and self.alt_text_generator.is_available():
                logger.info("Generating alt text with BLIP")
                image = Image.open(io.BytesIO(image_data))
                alt_text = self.alt_text_generator.generate_caption(image, context)
                return alt_text
            
            else:
                return "No AI models available for alt text generation"
            
        except Exception as e:
            logger.error(f"Failed to generate alt text: {e}")
            return f"Error generating alt text: {str(e)}"
    
    def suggest_heading_structure(self, text_blocks: List[Dict]) -> List[Dict]:
        """
        Analyze text blocks and suggest proper heading structure using AI when available
        """
        if not text_blocks:
            return []
        
        # Use Gemini for intelligent text classification if available
        if self.gemini_client and self.gemini_client.is_available() and self.ai_mode in ["gemini", "hybrid"]:
            logger.info("Using Gemini for heading structure analysis")
            try:
                classified_blocks = self.gemini_client.classify_text_elements(text_blocks)
                
                # Convert Gemini classifications to suggestions format
                suggestions = []
                for block in classified_blocks:
                    if block.get("ai_classification") and block["ai_classification"].startswith("H"):
                        suggestion = {
                            "page_num": block.get("page_num", 0),
                            "content": block.get("content", "").strip(),
                            "current_level": block.get("metadata", {}).get("heading_level", None),
                            "suggested_level": int(block["ai_classification"][1]),
                            "confidence": block.get("ai_confidence", 0.8),
                            "bbox": block.get("bbox", (0, 0, 0, 0)),
                            "ai_generated": True
                        }
                        suggestions.append(suggestion)
                
                logger.info(f"Generated {len(suggestions)} AI heading suggestions")
                return suggestions
                
            except Exception as e:
                logger.warning(f"Gemini heading analysis failed: {e}, falling back to rule-based approach")
        
        # Fallback to rule-based approach
        return self._rule_based_heading_analysis(text_blocks)
    
    def _rule_based_heading_analysis(self, text_blocks: List[Dict]) -> List[Dict]:
        """Original rule-based heading analysis as fallback"""
        suggestions = []
        
        # Analyze font sizes and text patterns
        font_sizes = []
        for block in text_blocks:
            if "font_size" in block.get("metadata", {}):
                font_sizes.append(block["metadata"]["font_size"])
        
        if not font_sizes:
            return suggestions
        
        avg_font_size = sum(font_sizes) / len(font_sizes)
        max_font_size = max(font_sizes)
        
        # Define heading levels based on font size
        heading_thresholds = {
            1: max_font_size,
            2: avg_font_size * 1.5,
            3: avg_font_size * 1.3,
            4: avg_font_size * 1.2,
            5: avg_font_size * 1.1,
            6: avg_font_size
        }
        
        for block in text_blocks:
            font_size = block.get("metadata", {}).get("font_size", avg_font_size)
            content = block.get("content", "").strip()
            
            # Skip if too long to be a heading
            if len(content) > 100 or len(content.split()) > 15:
                continue
            
            # Determine suggested heading level
            suggested_level = 6
            for level, threshold in heading_thresholds.items():
                if font_size >= threshold:
                    suggested_level = level
                    break
            
            # Additional heuristics
            if content.isupper() and not content.endswith('.'):
                suggested_level = max(1, suggested_level - 1)
            
            suggestion = {
                "page_num": block.get("page_num", 0),
                "content": content,
                "current_level": block.get("metadata", {}).get("heading_level", None),
                "suggested_level": suggested_level,
                "confidence": self._calculate_heading_confidence(block, suggested_level),
                "bbox": block.get("bbox", (0, 0, 0, 0)),
                "ai_generated": False
            }
            
            suggestions.append(suggestion)
        
        return suggestions
    
    def _calculate_heading_confidence(self, block: Dict, suggested_level: int) -> float:
        """Calculate confidence score for heading suggestion"""
        content = block.get("content", "").strip()
        font_size = block.get("metadata", {}).get("font_size", 12)
        
        confidence = 0.5  # Base confidence
        
        # Length factor
        if len(content) < 50:
            confidence += 0.2
        elif len(content) > 80:
            confidence -= 0.2
        
        # Font size factor
        if font_size > 16:
            confidence += 0.2
        elif font_size < 10:
            confidence -= 0.1
        
        # Content patterns
        if content.isupper():
            confidence += 0.1
        
        if not content.endswith('.'):
            confidence += 0.1
        
        if any(word in content.lower() for word in ["chapter", "section", "part"]):
            confidence += 0.2
        
        return min(1.0, max(0.0, confidence))
    
    def summarize_table(self, table_data: List[List[str]], context: str = "") -> str:
        """Generate a summary for a table using AI when available"""
        if not table_data:
            return "Empty table"
        
        # Use Gemini for intelligent table analysis if available
        if self.gemini_client and self.gemini_client.is_available() and self.ai_mode in ["gemini", "hybrid"]:
            try:
                logger.info("Using Gemini for table analysis")
                analysis = self.gemini_client.analyze_table_structure(table_data, context)
                
                # Extract summary from AI analysis
                ai_summary = analysis.get("summary", "")
                if ai_summary and not ai_summary.startswith("Error"):
                    return ai_summary
                else:
                    logger.warning("Gemini table analysis failed, falling back to rule-based approach")
                    
            except Exception as e:
                logger.warning(f"Gemini table analysis error: {e}, falling back to rule-based approach")
        
        # Fallback to rule-based table summarization
        return self._rule_based_table_summary(table_data)
    
    def _rule_based_table_summary(self, table_data: List[List[str]]) -> str:
        """Original rule-based table summary as fallback"""
        try:
            rows = len(table_data)
            cols = len(table_data[0]) if table_data else 0
            
            # Basic table description
            summary = f"Table with {rows} rows and {cols} columns"
            
            # Analyze first row as potential headers
            if rows > 1:
                headers = table_data[0]
                clean_headers = [str(h).strip() for h in headers if str(h).strip()]
                
                if clean_headers:
                    summary += f". Headers: {', '.join(clean_headers[:3])}"
                    if len(clean_headers) > 3:
                        summary += f" and {len(clean_headers) - 3} more"
            
            # Analyze data patterns
            if rows > 2:
                has_numbers = any(
                    any(str(cell).replace('.', '').replace(',', '').isdigit() 
                        for cell in row[1:] if cell)  # Skip first column
                    for row in table_data[1:3]  # Check first few data rows
                )
                
                if has_numbers:
                    summary += ". Contains numerical data"
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to summarize table: {e}")
            return "Table summary unavailable"
    
    def enhance_accessibility_fixes(self, issues: List[AccessibilityIssue], 
                                   pdf_images: List = None) -> List[AccessibilityIssue]:
        """Enhance issues with AI-generated suggestions"""
        if not self.is_available():
            logger.warning("AI models not available for enhancement")
            return issues
        
        enhanced_issues = []
        
        for issue in issues:
            enhanced_issue = issue
            
            try:
                # Generate alt text for images
                if (issue.element_type == "image" and 
                    "alt" in issue.issue_id.lower() and 
                    pdf_images is not None):
                    
                    # Find the corresponding image by image_id
                    image_id = issue.metadata.get("image_id", 0)
                    page_num = issue.page_num
                    
                    # Find matching image from PDF images
                    matching_image = None
                    for img in pdf_images:
                        if (img.page_num == page_num and 
                            img.image_id == image_id):
                            matching_image = img
                            break
                    
                    if matching_image and matching_image.image_data:
                        logger.info(f"Generating AI alt text for image {image_id} on page {page_num}")
                        alt_text = self.generate_alt_text(matching_image.image_data)
                        enhanced_issue.suggested_fix = alt_text
                        enhanced_issue.auto_fixable = True
                        logger.info(f"Generated alt text: {alt_text[:100]}...")
                
                # Enhance heading suggestions
                elif issue.element_type == "heading":
                    current_level = issue.metadata.get("current_level")
                    suggested_level = issue.metadata.get("suggested_level")
                    
                    if suggested_level:
                        enhanced_issue.suggested_fix = (
                            f"Change to H{suggested_level} based on content analysis"
                        )
                
                # Table summaries
                elif issue.element_type == "table" and "table_data" in issue.metadata:
                    table_data = issue.metadata["table_data"]
                    summary = self.summarize_table(table_data)
                    enhanced_issue.suggested_fix = f"Add table summary: {summary}"
                
            except Exception as e:
                logger.error(f"Failed to enhance issue {issue.issue_id}: {e}")
            
            enhanced_issues.append(enhanced_issue)
        
        return enhanced_issues
    
    def batch_generate_alt_text(self, images: List[Tuple[bytes, str]]) -> List[str]:
        """Generate alt text for multiple images"""
        if not self.is_available():
            return ["AI models not available"] * len(images)
        
        alt_texts = []
        
        for image_data, context in images:
            try:
                alt_text = self.generate_alt_text(image_data, context)
                alt_texts.append(alt_text)
            except Exception as e:
                logger.error(f"Failed to generate alt text in batch: {e}")
                alt_texts.append(f"Error: {str(e)}")
        
        return alt_texts
    
    def analyze_forms_with_ai(self, form_fields: List[Dict], analysis_context: Dict = None) -> Dict:
        """Analyze forms using AI-enhanced techniques"""
        form_analyzer = FormAnalyzer()
        analysis = form_analyzer.analyze_forms(form_fields, analysis_context)
        
        # Add AI enhancements if available
        if self.is_available() and form_fields:
            try:
                # Enhance field labeling suggestions
                for field_id, field_analysis in analysis.get('field_analysis', {}).items():
                    field_issues = field_analysis.get('issues', [])
                    
                    # Find the corresponding field
                    matching_field = None
                    for field in form_fields:
                        if f"{field.get('page_num', 0)}_{field.get('field_name', 'unnamed')}" == field_id:
                            matching_field = field
                            break
                    
                    if matching_field:
                        # Generate better label suggestions for unlabeled fields
                        field_name = matching_field.get('field_name', '')
                        field_type = matching_field.get('field_type', 'unknown')
                        
                        for issue in field_issues:
                            if issue.get('issue_type', '').startswith('PDF10_'):
                                if field_name:
                                    # Generate contextual label suggestion
                                    suggested_label = self._generate_contextual_label(field_name, field_type)
                                    if suggested_label:
                                        issue['ai_suggestion'] = f"Consider label: '{suggested_label}'"
                
                logger.info("Enhanced form analysis with AI suggestions")
            except Exception as e:
                logger.warning(f"Failed to add AI enhancements to form analysis: {e}")
        
        return analysis
    
    def _generate_contextual_label(self, field_name: str, field_type: str) -> str:
        """Generate contextual label suggestion based on field name and type"""
        # Simple rule-based label generation (could be enhanced with NLP)
        field_name_lower = field_name.lower()
        
        label_mappings = {
            'fname': 'First Name',
            'lname': 'Last Name',
            'email': 'Email Address',
            'phone': 'Phone Number',
            'addr': 'Address',
            'address': 'Street Address',
            'city': 'City',
            'state': 'State',
            'zip': 'ZIP Code',
            'country': 'Country',
            'dob': 'Date of Birth',
            'ssn': 'Social Security Number',
            'company': 'Company Name',
            'title': 'Job Title',
            'comment': 'Comments',
            'message': 'Message',
            'password': 'Password',
            'confirm': 'Confirm Password',
            'username': 'Username',
            'login': 'Login ID'
        }
        
        # Check for exact matches first
        if field_name_lower in label_mappings:
            return label_mappings[field_name_lower]
        
        # Check for partial matches
        for key, label in label_mappings.items():
            if key in field_name_lower:
                return label
        
        # Generate based on field type if no mapping found
        type_labels = {
            'text': 'Text Input',
            'password': 'Password',
            'checkbox': 'Checkbox',
            'radio': 'Radio Button',
            'dropdown': 'Select Option',
            'textarea': 'Text Area',
            'button': 'Button',
            'submit': 'Submit'
        }
        
        return type_labels.get(field_type, 'Input Field')
    
    def get_model_info(self) -> Dict:
        """Get information about loaded models"""
        info = {
            "initialized": self.initialized,
            "ai_mode": self.ai_mode,
            "models": {},
            "cost_tracking": {},
            "pdf_techniques_supported": [
                "PDF1 - Alt text generation (Enhanced with Gemini)",
                "PDF2 - Bookmark suggestions", 
                "PDF3 - Reading order optimization (Gemini)",
                "PDF6 - Table analysis (Enhanced with Gemini)",
                "PDF9 - Heading structure (Enhanced with Gemini)",
                "PDF10 - Form labeling",
                "PDF12 - Form accessibility",
                "PDF16 - Language detection"
            ]
        }
        
        if self.alt_text_generator:
            info["models"]["blip"] = {
                "model_name": self.alt_text_generator.model_name,
                "device": self.alt_text_generator.device,
                "available": self.alt_text_generator.is_available()
            }
        
        if self.gemini_client:
            info["models"]["gemini"] = {
                "model_name": self.gemini_client.model_name,
                "available": self.gemini_client.is_available(),
                "api_key_configured": self.gemini_client.api_key is not None
            }
            
            # Add cost tracking info
            if self.gemini_client.is_available():
                info["cost_tracking"] = self.gemini_client.get_cost_summary()
        
        return info
    
    def optimize_reading_order(self, elements: List[Dict]) -> List[Dict]:
        """Optimize reading order using AI analysis"""
        if not elements or not self.gemini_client or not self.gemini_client.is_available():
            return elements
        
        try:
            logger.info(f"Optimizing reading order for {len(elements)} elements with Gemini")
            optimized_elements = self.gemini_client.suggest_reading_order(elements)
            return optimized_elements
            
        except Exception as e:
            logger.error(f"Failed to optimize reading order: {e}")
            return elements
    
    def generate_document_accessibility_summary(self, document_info: Dict) -> str:
        """Generate comprehensive document accessibility summary"""
        if self.gemini_client and self.gemini_client.is_available():
            try:
                return self.gemini_client.generate_document_summary(document_info)
            except Exception as e:
                logger.warning(f"Failed to generate AI summary: {e}")
        
        # Fallback to basic summary
        total_issues = document_info.get("issues_count", 0)
        total_pages = document_info.get("total_pages", 0)
        
        if total_issues == 0:
            return f"Document appears to be accessibility compliant with no issues detected across {total_pages} pages."
        elif total_issues < 5:
            return f"Document has minor accessibility issues ({total_issues} issues) that can be easily remediated."
        else:
            return f"Document requires significant accessibility improvements ({total_issues} issues) across {total_pages} pages."
    
    def batch_process_images_for_alt_text(self, images: List[Tuple[bytes, str]], batch_size: int = 5) -> List[str]:
        """Process multiple images efficiently for alt text generation"""
        if not images:
            return []
        
        # Use Gemini batch processing if available for cost efficiency
        if self.gemini_client and self.gemini_client.is_available() and self.ai_mode in ["gemini", "hybrid"]:
            try:
                logger.info(f"Batch processing {len(images)} images with Gemini")
                return self.gemini_client.batch_process_images(images, batch_size)
            except Exception as e:
                logger.error(f"Gemini batch processing failed: {e}")
                if self.ai_mode == "hybrid" and self.alt_text_generator:
                    logger.info("Falling back to BLIP for batch processing")
        
        # Fallback to individual processing with BLIP
        if self.alt_text_generator and self.alt_text_generator.is_available():
            alt_texts = []
            for image_data, context in images:
                try:
                    image = Image.open(io.BytesIO(image_data))
                    alt_text = self.alt_text_generator.generate_caption(image, context)
                    alt_texts.append(alt_text)
                except Exception as e:
                    logger.error(f"Failed to process image: {e}")
                    alt_texts.append("Error generating alt text")
            
            return alt_texts
        
        return ["AI models not available"] * len(images)
    
    def get_ai_cost_summary(self) -> Dict:
        """Get comprehensive AI usage and cost summary"""
        summary = {
            "ai_mode": self.ai_mode,
            "models_available": [],
            "total_cost_usd": 0.0,
            "usage_stats": {}
        }
        
        if self.alt_text_generator and self.alt_text_generator.is_available():
            summary["models_available"].append("BLIP")
            summary["usage_stats"]["blip"] = "Local model - no API costs"
        
        if self.gemini_client and self.gemini_client.is_available():
            summary["models_available"].append("Gemini")
            gemini_costs = self.gemini_client.get_cost_summary()
            summary["total_cost_usd"] = gemini_costs["total_cost_usd"]
            summary["usage_stats"]["gemini"] = gemini_costs
        
        return summary
    
    def reset_ai_usage_tracking(self):
        """Reset AI usage and cost tracking"""
        if self.gemini_client:
            self.gemini_client.reset_cost_tracking()
        logger.info("Reset AI usage tracking")

    def classify_text_elements(self, elements: List[Dict]) -> List[Dict]:
        """
        Classify text elements using AI to identify headings, paragraphs, captions, etc.
        Delegates to Gemini client when available.
        """
        if not elements:
            return []

        # Use Gemini for intelligent text classification if available
        if self.gemini_client and self.gemini_client.is_available() and self.ai_mode in ["gemini", "hybrid"]:
            try:
                logger.info(f"Classifying {len(elements)} text elements with Gemini")
                return self.gemini_client.classify_text_elements(elements)
            except Exception as e:
                logger.error(f"Failed to classify text elements with Gemini: {e}")
                # Fall through to rule-based classification

        # Fallback to rule-based classification
        logger.info(f"Using rule-based classification for {len(elements)} text elements")
        return self._rule_based_text_classification(elements)

    def _rule_based_text_classification(self, elements: List[Dict]) -> List[Dict]:
        """
        Rule-based text classification as fallback when AI is not available
        """
        classified_elements = []

        for element in elements:
            classified = element.copy()
            content = element.get("content", "").strip()
            font_size = element.get("metadata", {}).get("font_size", 12)

            # Default classification
            classification = "P"  # Paragraph
            confidence = 0.5

            # Classify based on content and formatting
            if len(content) < 100:
                if font_size > 16:
                    classification = "H2"  # Large heading
                    confidence = 0.7
                elif font_size > 14:
                    classification = "H3"  # Medium heading
                    confidence = 0.6
                elif content.isupper() and len(content) < 50:
                    classification = "H4"  # Small heading
                    confidence = 0.6
                elif content.startswith("Figure") or content.startswith("Table"):
                    classification = "Caption"
                    confidence = 0.8
                elif content.startswith("Note:") or content.startswith("*"):
                    classification = "Note"
                    confidence = 0.7

            classified["ai_classification"] = classification
            classified["ai_confidence"] = confidence
            classified_elements.append(classified)

        return classified_elements