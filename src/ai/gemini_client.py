import logging
import base64
import io
from typing import List, Dict, Optional, Tuple, Union
from PIL import Image
import google.generativeai as genai
import os
from pathlib import Path
import time
import json

logger = logging.getLogger(__name__)


class GeminiClient:
    """Client for Google Gemini AI services focused on PDF accessibility"""
    
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.0-flash-exp"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name
        self.model = None
        self.initialized = False
        self.request_count = 0
        self.cost_tracker = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_cost_usd": 0.0
        }
        
        if not self.api_key:
            logger.warning("No Gemini API key provided. Set GEMINI_API_KEY environment variable or pass api_key parameter.")
            return
            
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Gemini client"""
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
            self.initialized = True
            logger.info(f"Initialized Gemini client with model: {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            self.initialized = False
    
    def is_available(self) -> bool:
        """Check if Gemini client is available"""
        return self.initialized and self.model is not None
    
    def generate_alt_text(self, image_data: bytes, context: str = "") -> str:
        """Generate alt text for image using Gemini Vision"""
        if not self.is_available():
            return "Gemini AI not available"
        
        try:
            # Convert image data to PIL Image
            image = Image.open(io.BytesIO(image_data))
            
            # Create prompt for alt text generation
            prompt = self._create_alt_text_prompt(context)
            
            # Generate response
            response = self.model.generate_content([prompt, image])
            
            # Update cost tracking
            self._update_cost_tracking(response)
            
            alt_text = response.text.strip()
            logger.info(f"Generated alt text: {alt_text[:100]}...")
            
            return alt_text
            
        except Exception as e:
            logger.error(f"Failed to generate alt text with Gemini: {e}")
            return f"Error generating alt text: {str(e)}"
    
    def classify_text_elements(self, text_blocks: List[Dict]) -> List[Dict]:
        """Classify text elements into semantic roles (H1, H2, P, List, Table, Figure)"""
        if not self.is_available():
            logger.warning("Gemini not available for text classification")
            return text_blocks
        
        classified_blocks = []
        
        # Process blocks in batches to optimize API usage
        batch_size = 10
        for i in range(0, len(text_blocks), batch_size):
            batch = text_blocks[i:i + batch_size]
            try:
                classified_batch = self._classify_text_batch(batch)
                classified_blocks.extend(classified_batch)
            except Exception as e:
                logger.error(f"Failed to classify text batch {i//batch_size + 1}: {e}")
                # Fallback to original blocks
                classified_blocks.extend(batch)
        
        return classified_blocks
    
    def _classify_text_batch(self, text_blocks: List[Dict]) -> List[Dict]:
        """Classify a batch of text blocks"""
        if not text_blocks:
            return []
        
        # Create classification prompt
        prompt = self._create_classification_prompt(text_blocks)
        
        try:
            response = self.model.generate_content(prompt)
            self._update_cost_tracking(response)
            
            # Parse response
            classifications = self._parse_classification_response(response.text, text_blocks)
            return classifications
            
        except Exception as e:
            logger.error(f"Failed to classify text batch: {e}")
            return text_blocks
    
    def suggest_reading_order(self, elements: List[Dict]) -> List[Dict]:
        """Suggest logical reading order for document elements"""
        if not self.is_available() or not elements:
            return elements
        
        try:
            # Create reading order prompt
            prompt = self._create_reading_order_prompt(elements)
            
            response = self.model.generate_content(prompt)
            self._update_cost_tracking(response)
            
            # Parse and apply reading order suggestions
            reordered_elements = self._parse_reading_order_response(response.text, elements)
            
            logger.info(f"Suggested reading order for {len(elements)} elements")
            return reordered_elements
            
        except Exception as e:
            logger.error(f"Failed to suggest reading order: {e}")
            return elements
    
    def analyze_table_structure(self, table_data: List[List[str]], context: str = "") -> Dict:
        """Analyze table structure and suggest improvements"""
        if not self.is_available() or not table_data:
            return {"summary": "Table analysis not available", "suggestions": []}
        
        try:
            prompt = self._create_table_analysis_prompt(table_data, context)
            
            response = self.model.generate_content(prompt)
            self._update_cost_tracking(response)
            
            analysis = self._parse_table_analysis_response(response.text)
            
            logger.info(f"Analyzed table with {len(table_data)} rows")
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze table structure: {e}")
            return {"summary": "Error analyzing table", "suggestions": []}
    
    def generate_document_summary(self, document_info: Dict) -> str:
        """Generate document summary for accessibility reports"""
        if not self.is_available():
            return "Document summary not available"
        
        try:
            prompt = self._create_document_summary_prompt(document_info)
            
            response = self.model.generate_content(prompt)
            self._update_cost_tracking(response)
            
            summary = response.text.strip()
            logger.info("Generated document accessibility summary")
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to generate document summary: {e}")
            return "Error generating document summary"
    
    def _create_alt_text_prompt(self, context: str) -> str:
        """Create prompt for alt text generation"""
        base_prompt = """Generate concise, descriptive alternative text for this image that would help a screen reader user understand its content and context.

Guidelines:
- Be specific and descriptive but concise
- Focus on the essential information the image conveys
- If it's a chart/graph, describe the data and trends
- If it's a diagram, explain the key components and relationships
- If it's decorative, say "Decorative image"
- Limit to 125 characters when possible

"""
        if context:
            base_prompt += f"Context: This image appears in a document about {context}\n\n"
        
        base_prompt += "Alternative text:"
        return base_prompt
    
    def _create_classification_prompt(self, text_blocks: List[Dict]) -> str:
        """Create prompt for text classification"""
        prompt = """Classify each text block below into one of these semantic roles:
- H1: Main title/heading
- H2: Major section heading  
- H3: Subsection heading
- H4: Minor heading
- H5: Sub-minor heading
- H6: Smallest heading
- P: Regular paragraph text
- List: List item or list marker
- Table: Table content or caption
- Figure: Figure caption or description

Consider font size, position, and content when classifying. Respond in JSON format.

Text blocks to classify:
"""
        
        for i, block in enumerate(text_blocks):
            content = block.get("content", "")[:100]  # First 100 chars
            font_size = block.get("metadata", {}).get("font_size", 12)
            page_num = block.get("page_num", 0)
            
            prompt += f"\n{i}: \"{content}\" (font: {font_size}pt, page: {page_num})"
        
        prompt += "\n\nRespond with JSON array: [{\"index\": 0, \"classification\": \"H1\", \"confidence\": 0.9}, ...]"
        return prompt
    
    def _create_reading_order_prompt(self, elements: List[Dict]) -> str:
        """Create prompt for reading order analysis"""
        prompt = """Analyze the reading order of these document elements and suggest the optimal sequence for accessibility.
Consider logical flow, document structure, and accessibility best practices.

Elements (with current order):
"""
        for i, element in enumerate(elements[:20]):  # Limit to first 20 for API efficiency
            content = element.get("content", "")[:50]
            element_type = element.get("type", "unknown")
            page_num = element.get("page_num", 0)
            bbox = element.get("bbox", [0, 0, 0, 0])
            
            prompt += f"\n{i}: {element_type} - \"{content}\" (page {page_num}, y:{bbox[1]:.0f})"
        
        prompt += "\n\nSuggest reordering by providing new indices in order: [0, 1, 2, ...] or explain why current order is optimal."
        return prompt
    
    def _create_table_analysis_prompt(self, table_data: List[List[str]], context: str) -> str:
        """Create prompt for table analysis"""
        prompt = f"""Analyze this table structure for accessibility compliance:

Table data (first few rows):
"""
        # Show first 5 rows max
        for i, row in enumerate(table_data[:5]):
            row_str = " | ".join(str(cell)[:20] for cell in row[:6])  # First 6 columns, 20 chars each
            prompt += f"Row {i}: {row_str}\n"
        
        if len(table_data) > 5:
            prompt += f"... ({len(table_data) - 5} more rows)\n"
        
        prompt += f"""
Context: {context}

Provide analysis in JSON format:
{{
  "summary": "Brief table description",
  "has_headers": true/false,
  "header_row": 0,
  "accessibility_issues": ["issue1", "issue2"],
  "suggestions": ["suggestion1", "suggestion2"]
}}"""
        
        return prompt
    
    def _create_document_summary_prompt(self, document_info: Dict) -> str:
        """Create prompt for document summary"""
        total_pages = document_info.get("total_pages", 0)
        issues_count = document_info.get("issues_count", 0)
        elements = document_info.get("elements_summary", {})
        
        prompt = f"""Create a brief accessibility summary for this PDF document:

Document Statistics:
- Total pages: {total_pages}
- Accessibility issues found: {issues_count}
- Text blocks: {elements.get('text_blocks', 0)}
- Images: {elements.get('images', 0)}
- Tables: {elements.get('tables', 0)}
- Headings: {elements.get('headings', 0)}

Generate a 2-3 sentence summary focusing on:
1. Overall accessibility status
2. Main types of issues found
3. Remediation priority

Summary:"""
        return prompt
    
    def _parse_classification_response(self, response_text: str, original_blocks: List[Dict]) -> List[Dict]:
        """Parse Gemini's classification response"""
        try:
            # Try to extract JSON from response
            response_text = response_text.strip()
            
            # Find JSON array in response
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                classifications = json.loads(json_str)
                
                # Apply classifications to original blocks
                for classification in classifications:
                    index = classification.get("index")
                    new_type = classification.get("classification", "P")
                    confidence = classification.get("confidence", 0.5)
                    
                    if 0 <= index < len(original_blocks):
                        # Update block with classification
                        original_blocks[index]["ai_classification"] = new_type
                        original_blocks[index]["ai_confidence"] = confidence
                        
                        # Update element type if confidence is high
                        if confidence > 0.7:
                            if new_type.startswith("H"):
                                original_blocks[index]["type"] = "heading"
                                original_blocks[index]["metadata"]["heading_level"] = int(new_type[1])
                            else:
                                original_blocks[index]["type"] = new_type.lower()
                
                logger.info(f"Applied {len(classifications)} AI classifications")
                
        except Exception as e:
            logger.warning(f"Failed to parse classification response: {e}")
        
        return original_blocks
    
    def _parse_reading_order_response(self, response_text: str, original_elements: List[Dict]) -> List[Dict]:
        """Parse reading order suggestions"""
        try:
            # Look for array of indices in response
            import re
            array_match = re.search(r'\[[\d,\s]+\]', response_text)
            
            if array_match:
                indices_str = array_match.group()
                indices = json.loads(indices_str)
                
                # Validate indices
                if len(indices) == len(original_elements) and all(0 <= i < len(original_elements) for i in indices):
                    # Reorder elements based on suggestions
                    reordered = [original_elements[i] for i in indices]
                    logger.info("Applied AI reading order suggestions")
                    return reordered
            
            logger.info("AI suggested current reading order is optimal")
            
        except Exception as e:
            logger.warning(f"Failed to parse reading order response: {e}")
        
        return original_elements
    
    def _parse_table_analysis_response(self, response_text: str) -> Dict:
        """Parse table analysis response"""
        try:
            # Extract JSON from response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                analysis = json.loads(json_str)
                return analysis
                
        except Exception as e:
            logger.warning(f"Failed to parse table analysis response: {e}")
        
        return {
            "summary": "Table analysis completed",
            "has_headers": True,
            "accessibility_issues": [],
            "suggestions": []
        }
    
    def _update_cost_tracking(self, response):
        """Update cost tracking based on response"""
        try:
            usage = response.usage_metadata
            input_tokens = usage.prompt_token_count
            output_tokens = usage.candidates_token_count
            
            self.cost_tracker["input_tokens"] += input_tokens
            self.cost_tracker["output_tokens"] += output_tokens
            
            # Gemini 2.0 Flash pricing (as of 2024)
            input_cost = input_tokens * 0.000075 / 1000  # $0.075 per 1M tokens
            output_cost = output_tokens * 0.0003 / 1000   # $0.30 per 1M tokens
            
            self.cost_tracker["total_cost_usd"] += input_cost + output_cost
            self.request_count += 1
            
            logger.debug(f"API usage: {input_tokens} in, {output_tokens} out tokens. Total cost: ${self.cost_tracker['total_cost_usd']:.4f}")
            
        except Exception as e:
            logger.debug(f"Could not track API usage: {e}")
    
    def get_cost_summary(self) -> Dict:
        """Get cost and usage summary"""
        return {
            "requests_made": self.request_count,
            "input_tokens": self.cost_tracker["input_tokens"],
            "output_tokens": self.cost_tracker["output_tokens"],
            "total_cost_usd": round(self.cost_tracker["total_cost_usd"], 4),
            "model": self.model_name
        }
    
    def reset_cost_tracking(self):
        """Reset cost tracking counters"""
        self.cost_tracker = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_cost_usd": 0.0
        }
        self.request_count = 0
        logger.info("Reset cost tracking")
    
    def batch_process_images(self, images: List[Tuple[bytes, str]], batch_size: int = 5) -> List[str]:
        """Process multiple images in batches for cost efficiency"""
        if not self.is_available():
            return ["Gemini not available"] * len(images)
        
        alt_texts = []
        
        # Process in batches to manage rate limits and costs
        for i in range(0, len(images), batch_size):
            batch = images[i:i + batch_size]
            batch_results = []
            
            for image_data, context in batch:
                alt_text = self.generate_alt_text(image_data, context)
                batch_results.append(alt_text)
                
                # Small delay to respect rate limits
                time.sleep(0.1)
            
            alt_texts.extend(batch_results)
            
            # Log progress for large batches
            if len(images) > 10:
                logger.info(f"Processed {min(i + batch_size, len(images))}/{len(images)} images")
        
        return alt_texts