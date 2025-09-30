import fitz  # PyMuPDF
import io
from PIL import Image
from typing import List, Dict, Tuple, Optional
import logging
import re
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PDFElement:
    def __init__(self, element_type: str, bbox: Tuple[float, float, float, float], 
                 page_num: int, content: str = "", metadata: Dict = None):
        self.type = element_type
        self.bbox = bbox  # (x0, y0, x1, y1)
        self.page_num = page_num
        self.content = content
        self.metadata = metadata or {}


class PDFImage:
    def __init__(self, image_data: bytes, bbox: Tuple[float, float, float, float], 
                 page_num: int, alt_text: str = "", image_id: int = 0):
        self.image_data = image_data
        self.bbox = bbox
        self.page_num = page_num
        self.alt_text = alt_text
        self.image_id = image_id
        self.pil_image = None
        # Additional accessibility metadata
        self.is_decorative = False
        self.has_alt_in_xobject = False
        self.has_alt_in_structure = False
        self._load_pil_image()
    
    def _load_pil_image(self):
        try:
            self.pil_image = Image.open(io.BytesIO(self.image_data))
        except Exception as e:
            logger.warning(f"Failed to load image: {e}")


class PDFParser:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.doc = None
        self.metadata = {}
        self.pages_analyzed = 0
        self._open_document()
    
    def _open_document(self):
        try:
            self.doc = fitz.open(self.pdf_path)
            self.metadata = self.doc.metadata
            logger.info(f"Opened PDF: {self.pdf_path} with {len(self.doc)} pages")
        except Exception as e:
            logger.error(f"Failed to open PDF: {e}")
            raise
    
    def close(self):
        if self.doc:
            self.doc.close()
    
    def extract_text_blocks(self, page_num: int = None) -> List[PDFElement]:
        text_blocks = []
        pages = [self.doc[page_num]] if page_num is not None else self.doc
        
        for page in pages:
            blocks = page.get_text("dict")
            
            for block in blocks["blocks"]:
                if "lines" in block:  # Text block
                    bbox = (block["bbox"][0], block["bbox"][1], 
                           block["bbox"][2], block["bbox"][3])
                    
                    text_content = ""
                    font_sizes = []
                    
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text_content += span["text"]
                            font_sizes.append(span["size"])
                    
                    avg_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 12
                    
                    element = PDFElement(
                        element_type="text",
                        bbox=bbox,
                        page_num=page.number,
                        content=text_content.strip(),
                        metadata={"font_size": avg_font_size, "font_sizes": font_sizes}
                    )
                    
                    if element.content:  # Only add non-empty text blocks
                        text_blocks.append(element)
        
        return text_blocks
    
    def extract_images(self, page_num: int = None) -> List[PDFImage]:
        images = []
        pages = [self.doc[page_num]] if page_num is not None else self.doc
        
        for page in pages:
            image_list = page.get_images()
            
            for img_index, img in enumerate(image_list):
                try:
                    # Get image data
                    xref = img[0]
                    pix = fitz.Pixmap(self.doc, xref)
                    
                    if pix.n - pix.alpha < 4:  # GRAY or RGB
                        img_data = pix.tobytes("png")
                    else:  # CMYK: convert to RGB first
                        pix1 = fitz.Pixmap(fitz.csRGB, pix)
                        img_data = pix1.tobytes("png")
                        pix1 = None
                    
                    pix = None
                    
                    # Get image bbox (approximate)
                    image_rects = page.get_image_rects(xref)
                    bbox = image_rects[0] if image_rects else (0, 0, 100, 100)
                    
                    # Extract alt text from PDF structure
                    alt_text = self._extract_image_alt_text(xref, page, bbox)
                    
                    # Check if image is marked as artifact (decorative)
                    is_decorative = self._check_if_artifact(page, bbox)
                    
                    pdf_image = PDFImage(
                        image_data=img_data,
                        bbox=bbox,
                        page_num=page.number,
                        alt_text=alt_text,
                        image_id=img_index
                    )
                    
                    # Add metadata about the image's accessibility status
                    pdf_image.is_decorative = is_decorative
                    pdf_image.has_alt_in_xobject = self._check_alt_in_xobject(xref)
                    pdf_image.has_alt_in_structure = self._check_alt_in_structure_tree(page, bbox)
                    
                    images.append(pdf_image)
                    
                except Exception as e:
                    logger.warning(f"Failed to extract image {img_index} on page {page.number}: {e}")
                    continue
        
        return images
    
    def _extract_image_alt_text(self, xref: int, page, bbox: Tuple) -> str:
        """Extract alt text from various sources in PDF structure"""
        # Try method 1: Check XObject dictionary for /Alt entry
        try:
            xref_obj = self.doc.xref_object(xref)
            if xref_obj and "/Alt" in xref_obj:
                # Extract alt text from XObject
                alt_match = re.search(r'/Alt\s*\((.*?)\)', xref_obj)
                if alt_match:
                    return alt_match.group(1)
        except Exception as e:
            logger.debug(f"Could not check XObject for alt text: {e}")
        
        # Try method 2: Check structure tree for alt text
        try:
            # Get page content and look for marked content with Alt
            contents = page.read_contents()
            if contents:
                content_str = contents.decode('utf-8', errors='ignore')
                # Look for marked content with /Alt property near the image location
                alt_pattern = r'/Alt\s*\((.*?)\)\s*>>\s*BDC'
                matches = re.findall(alt_pattern, content_str)
                if matches:
                    return matches[0]
        except Exception as e:
            logger.debug(f"Could not check page contents for alt text: {e}")
        
        # Try method 3: Check parent structure elements
        try:
            # This would require more complex structure tree navigation
            # For now, return empty if no alt text found
            pass
        except Exception:
            pass
        
        return ""
    
    def _check_alt_in_xobject(self, xref: int) -> bool:
        """Check if image has /Alt entry in its XObject dictionary"""
        try:
            xref_obj = self.doc.xref_object(xref)
            return xref_obj and "/Alt" in xref_obj
        except Exception:
            return False
    
    def _check_alt_in_structure_tree(self, page, bbox: Tuple) -> bool:
        """Check if image has alt text in structure tree"""
        try:
            # Check for marked content with Alt property
            contents = page.read_contents()
            if contents:
                content_str = contents.decode('utf-8', errors='ignore')
                # Simple check for Alt property in marked content
                return "/Alt" in content_str and "BDC" in content_str
        except Exception:
            return False
        
        return False
    
    def _check_if_artifact(self, page, bbox: Tuple) -> bool:
        """Check if image is marked as an artifact (decorative)"""
        try:
            # Check page content for artifact marking
            contents = page.read_contents()
            if contents:
                content_str = contents.decode('utf-8', errors='ignore')
                # Look for artifact marking
                # PDF syntax: /Artifact ... BMC ... EMC
                return "/Artifact" in content_str and "BMC" in content_str
        except Exception:
            return False
        
        return False
    
    def detect_headings(self, text_blocks: List[PDFElement]) -> List[PDFElement]:
        if not text_blocks:
            return []
        
        # Calculate average font size
        font_sizes = [block.metadata.get("font_size", 12) for block in text_blocks]
        avg_font_size = sum(font_sizes) / len(font_sizes)
        
        headings = []
        
        for block in text_blocks:
            font_size = block.metadata.get("font_size", 12)
            content = block.content.strip()
            
            # Heuristics for heading detection
            is_heading = False
            heading_level = 6  # Default to H6
            
            # Font size based detection
            if font_size > avg_font_size * 1.5:
                is_heading = True
                heading_level = 1
            elif font_size > avg_font_size * 1.3:
                is_heading = True
                heading_level = 2
            elif font_size > avg_font_size * 1.2:
                is_heading = True
                heading_level = 3
            elif font_size > avg_font_size * 1.1:
                is_heading = True
                heading_level = 4
            
            # Additional heuristics
            if (len(content) < 100 and  # Short text
                content.isupper() and  # All caps
                not content.endswith('.') and  # No period
                len(content.split()) < 10):  # Few words
                is_heading = True
                if heading_level > 4:
                    heading_level = 5
            
            if is_heading:
                heading = PDFElement(
                    element_type="heading",
                    bbox=block.bbox,
                    page_num=block.page_num,
                    content=content,
                    metadata={
                        "font_size": font_size,
                        "heading_level": heading_level,
                        "original_type": "text"
                    }
                )
                headings.append(heading)
        
        return headings
    
    def detect_tables(self, page_num: int = None) -> List[PDFElement]:
        tables = []
        pages = [self.doc[page_num]] if page_num is not None else self.doc
        
        for page in pages:
            try:
                # Simple table detection using PyMuPDF
                tabs = page.find_tables()
                
                for i, tab in enumerate(tabs):
                    table_data = tab.extract()
                    bbox = tab.bbox
                    
                    table = PDFElement(
                        element_type="table",
                        bbox=bbox,
                        page_num=page.number,
                        content=str(table_data),
                        metadata={
                            "table_id": i,
                            "rows": len(table_data),
                            "columns": len(table_data[0]) if table_data else 0,
                            "data": table_data
                        }
                    )
                    tables.append(table)
                    
            except Exception as e:
                logger.warning(f"Failed to extract tables from page {page.number}: {e}")
        
        return tables
    
    def get_reading_order(self, elements: List[PDFElement]) -> List[PDFElement]:
        if not elements:
            return elements
        
        # Sort by page, then by Y position (top to bottom), then by X position (left to right)
        sorted_elements = sorted(elements, key=lambda e: (e.page_num, -e.bbox[1], e.bbox[0]))
        
        return sorted_elements
    
    def extract_bookmarks(self) -> List[Dict]:
        """Extract document bookmarks (PDF2 technique)"""
        bookmarks = []
        if not self.doc:
            return bookmarks
        
        try:
            toc = self.doc.get_toc()
            for level, title, page_num in toc:
                bookmarks.append({
                    "level": level,
                    "title": title.strip(),
                    "page_num": page_num - 1,  # Convert to 0-based indexing
                    "type": "bookmark"
                })
            logger.info(f"Extracted {len(bookmarks)} bookmarks")
        except Exception as e:
            logger.warning(f"Failed to extract bookmarks: {e}")
        
        return bookmarks
    
    def extract_form_fields(self) -> List[Dict]:
        """Extract form fields for PDF10, PDF12, PDF15, PDF22, PDF23 techniques"""
        form_fields = []
        if not self.doc:
            return form_fields
        
        try:
            for page_num in range(len(self.doc)):
                page = self.doc[page_num]
                widgets = page.widgets()
                
                for widget in widgets:
                    field_info = {
                        "page_num": page_num,
                        "bbox": widget.rect,
                        "field_name": widget.field_name or "",
                        "field_type": widget.field_type_string or "unknown",
                        "field_value": widget.field_value or "",
                        "field_label": widget.field_label or "",
                        "is_required": getattr(widget, 'field_flags', 0) & 2 != 0,  # Required flag
                        "is_readonly": getattr(widget, 'field_flags', 0) & 1 != 0,   # Readonly flag
                        "tooltip": getattr(widget, 'tooltip', ''),
                        "type": "form_field"
                    }
                    form_fields.append(field_info)
            
            logger.info(f"Extracted {len(form_fields)} form fields")
        except Exception as e:
            logger.warning(f"Failed to extract form fields: {e}")
        
        return form_fields
    
    def extract_links(self) -> List[Dict]:
        """Extract links for PDF11, PDF13 techniques"""
        links = []
        if not self.doc:
            return links
        
        try:
            for page_num in range(len(self.doc)):
                page = self.doc[page_num]
                page_links = page.get_links()
                
                for link in page_links:
                    link_info = {
                        "page_num": page_num,
                        "bbox": link.get('from', (0, 0, 0, 0)),
                        "uri": link.get('uri', ''),
                        "dest": link.get('page', -1),
                        "link_text": self._extract_link_text(page, link.get('from', (0, 0, 0, 0))),
                        "type": "link"
                    }
                    links.append(link_info)
            
            logger.info(f"Extracted {len(links)} links")
        except Exception as e:
            logger.warning(f"Failed to extract links: {e}")
        
        return links
    
    def _extract_link_text(self, page, bbox) -> str:
        """Extract text content from link area"""
        try:
            rect = fitz.Rect(bbox)
            text_instances = page.get_text("dict", clip=rect)
            text = ""
            for block in text_instances.get("blocks", []):
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text += span["text"]
            return text.strip()
        except Exception:
            return ""
    
    def extract_lists(self) -> List[Dict]:
        """Extract list structures for PDF21 technique"""
        lists = []
        if not self.doc:
            return lists
        
        try:
            # This is a simplified list detection based on text patterns
            # In a full implementation, you would analyze PDF structure tree
            text_blocks = self.extract_text_blocks()
            
            current_list = None
            list_id = 0
            
            for block in text_blocks:
                content = block.content.strip()
                if self._is_list_item(content):
                    if current_list is None:
                        current_list = {
                            "list_id": list_id,
                            "page_num": block.page_num,
                            "bbox": block.bbox,
                            "items": [],
                            "list_type": self._detect_list_type(content),
                            "type": "list"
                        }
                        list_id += 1
                    
                    current_list["items"].append({
                        "content": content,
                        "bbox": block.bbox,
                        "page_num": block.page_num
                    })
                else:
                    if current_list and len(current_list["items"]) > 1:
                        lists.append(current_list)
                    current_list = None
            
            # Add final list if exists
            if current_list and len(current_list["items"]) > 1:
                lists.append(current_list)
            
            logger.info(f"Detected {len(lists)} lists")
        except Exception as e:
            logger.warning(f"Failed to extract lists: {e}")
        
        return lists
    
    def _is_list_item(self, text: str) -> bool:
        """Detect if text looks like a list item"""
        if not text:
            return False
        
        # Check for common list markers
        list_patterns = [
            r'^[•·▪▫▴▸‣⁃]\s+',  # Bullet points
            r'^[-*+]\s+',        # Dash/asterisk/plus bullets
            r'^\d+[.):]\s+',     # Numbered lists (1. 1) 1:)
            r'^[a-zA-Z][.):]\s+', # Lettered lists (a. a) a:)
            r'^[ivxlcdm]+[.):]\s+', # Roman numerals
        ]
        
        for pattern in list_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def _detect_list_type(self, text: str) -> str:
        """Detect type of list (bulleted, numbered, etc.)"""
        if re.match(r'^[•·▪▫▴▸‣⁃\-*+]\s+', text):
            return "bulleted"
        elif re.match(r'^\d+[.):]\s+', text):
            return "numbered"
        elif re.match(r'^[a-zA-Z][.):]\s+', text):
            return "lettered" 
        elif re.match(r'^[ivxlcdm]+[.):]\s+', text, re.IGNORECASE):
            return "roman"
        else:
            return "unknown"
    
    def extract_document_language(self) -> str:
        """Extract document language for PDF16 technique"""
        try:
            # Try to get language from document catalog
            catalog = self.doc._getOLRootNumber()
            if catalog:
                # This would require deeper PDF structure analysis
                # For now, return from metadata if available
                return self.metadata.get('language', '')
            
            # Fallback: try to detect language from text content
            return self._detect_text_language()
        except Exception as e:
            logger.warning(f"Failed to extract document language: {e}")
            return ""
    
    def _detect_text_language(self) -> str:
        """Simple language detection from text content"""
        try:
            # Get sample text from first few pages
            sample_text = ""
            for page_num in range(min(3, len(self.doc))):
                page_text = self.doc[page_num].get_text()
                sample_text += page_text[:1000]  # First 1000 chars per page
            
            # Very basic language detection (would need proper NLP library in production)
            if not sample_text.strip():
                return "unknown"
            
            # Count common words in different languages
            english_words = ['the', 'and', 'or', 'of', 'to', 'in', 'a', 'is']
            spanish_words = ['el', 'la', 'y', 'de', 'que', 'a', 'en', 'un']
            french_words = ['le', 'de', 'et', 'à', 'un', 'il', 'être', 'et']
            
            sample_lower = sample_text.lower()
            english_count = sum(1 for word in english_words if word in sample_lower)
            spanish_count = sum(1 for word in spanish_words if word in sample_lower) 
            french_count = sum(1 for word in french_words if word in sample_lower)
            
            if english_count >= spanish_count and english_count >= french_count:
                return "en"
            elif spanish_count >= french_count:
                return "es"
            elif french_count > 0:
                return "fr"
            
            return "unknown"
        except Exception:
            return "unknown"
    
    def detect_scanned_content(self) -> List[Dict]:
        """Detect scanned pages for PDF7 technique"""
        scanned_pages = []
        if not self.doc:
            return scanned_pages
        
        try:
            for page_num in range(len(self.doc)):
                page = self.doc[page_num]
                
                # Get text content
                text_content = page.get_text().strip()
                
                # Get images
                images = page.get_images()
                
                # Heuristic: if page has large images but little text, likely scanned
                if len(images) > 0 and len(text_content) < 50:
                    # Check if images cover most of the page
                    page_area = abs(page.rect.width * page.rect.height)
                    image_area = 0
                    
                    for img in images:
                        try:
                            image_rects = page.get_image_rects(img[0])
                            for rect in image_rects:
                                image_area += abs(rect.width * rect.height)
                        except Exception:
                            continue
                    
                    if image_area > page_area * 0.7:  # Image covers >70% of page
                        scanned_pages.append({
                            "page_num": page_num,
                            "text_length": len(text_content),
                            "image_count": len(images),
                            "image_coverage": image_area / page_area if page_area > 0 else 0,
                            "type": "scanned_page"
                        })
            
            logger.info(f"Detected {len(scanned_pages)} potentially scanned pages")
        except Exception as e:
            logger.warning(f"Failed to detect scanned content: {e}")
        
        return scanned_pages
    
    def analyze_document(self) -> Dict:
        logger.info("Starting comprehensive document analysis...")
        
        # Extract all elements
        text_blocks = self.extract_text_blocks()
        images = self.extract_images()
        tables = self.detect_tables()
        headings = self.detect_headings(text_blocks)
        
        # New PDF technique extractions
        bookmarks = self.extract_bookmarks()
        form_fields = self.extract_form_fields()
        links = self.extract_links()
        lists = self.extract_lists()
        document_language = self.extract_document_language()
        scanned_pages = self.detect_scanned_content()
        
        # Get reading order
        all_text_elements = text_blocks + headings + tables
        reading_order = self.get_reading_order(all_text_elements)
        
        analysis = {
            "metadata": self.metadata,
            "total_pages": len(self.doc),
            "text_blocks": text_blocks,
            "images": images,
            "tables": tables,
            "headings": headings,
            "reading_order": reading_order,
            "bookmarks": bookmarks,
            "form_fields": form_fields,
            "links": links,
            "lists": lists,
            "document_language": document_language,
            "scanned_pages": scanned_pages,
            "statistics": {
                "text_blocks_count": len(text_blocks),
                "images_count": len(images),
                "tables_count": len(tables),
                "headings_count": len(headings),
                "bookmarks_count": len(bookmarks),
                "form_fields_count": len(form_fields),
                "links_count": len(links),
                "lists_count": len(lists),
                "scanned_pages_count": len(scanned_pages)
            }
        }
        
        logger.info(f"Analysis complete. Found {len(text_blocks)} text blocks, "
                   f"{len(images)} images, {len(tables)} tables, {len(headings)} headings, "
                   f"{len(bookmarks)} bookmarks, {len(form_fields)} form fields, "
                   f"{len(links)} links, {len(lists)} lists")
        
        return analysis