"""
JSON Schema for PDF Accessibility Tag Tree
Provides a standardized format for representing PDF document structure
with accessibility metadata and AI enhancement tracking.
"""

import json
import uuid
from typing import Dict, List, Optional, Union, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class NodeStatus(Enum):
    """Status of accessibility tag node"""
    OK = "ok"
    AI_SUGGESTED = "ai-suggested"  
    MANUAL_REVIEW = "manual-review"
    ERROR = "error"
    FIXED = "fixed"


class NodeType(Enum):
    """PDF accessibility tag types"""
    DOCUMENT = "Document"
    H1 = "H1"
    H2 = "H2"  
    H3 = "H3"
    H4 = "H4"
    H5 = "H5"
    H6 = "H6"
    P = "P"
    FIGURE = "Figure"
    LIST = "List"
    LI = "LI"
    TABLE = "Table"
    TR = "TR"
    TH = "TH"
    TD = "TD"
    LINK = "Link"
    FORM = "Form"
    ARTIFACT = "Artifact"
    

@dataclass
class BoundingBox:
    """Bounding box coordinates in PDF space"""
    x0: float
    y0: float
    x1: float
    y1: float
    
    def to_list(self) -> List[float]:
        return [self.x0, self.y0, self.x1, self.y1]
    
    @classmethod
    def from_list(cls, bbox_list: List[float]) -> 'BoundingBox':
        return cls(bbox_list[0], bbox_list[1], bbox_list[2], bbox_list[3])
    
    def area(self) -> float:
        return abs((self.x1 - self.x0) * (self.y1 - self.y0))


@dataclass
class AccessibilityNode:
    """Individual node in the accessibility tag tree"""
    id: str
    type: NodeType
    page: int
    bbox: BoundingBox
    status: NodeStatus = NodeStatus.OK
    text: Optional[str] = None
    alt_text: Optional[str] = None
    children: List['AccessibilityNode'] = None
    
    # AI enhancement metadata
    ai_confidence: Optional[float] = None
    ai_suggestion: Optional[str] = None
    ai_generated: bool = False
    
    # PDF technique compliance
    pdf_techniques: List[str] = None
    wcag_criteria: List[str] = None
    
    # User interaction
    user_modified: bool = False
    last_modified: Optional[str] = None
    
    def __post_init__(self):
        if self.children is None:
            self.children = []
        if self.pdf_techniques is None:
            self.pdf_techniques = []
        if self.wcag_criteria is None:
            self.wcag_criteria = []
        if self.last_modified is None:
            self.last_modified = datetime.now().isoformat()
    
    def add_child(self, child: 'AccessibilityNode'):
        """Add child node"""
        self.children.append(child)
        self.last_modified = datetime.now().isoformat()
    
    def remove_child(self, child_id: str) -> bool:
        """Remove child by ID"""
        for i, child in enumerate(self.children):
            if child.id == child_id:
                del self.children[i]
                self.last_modified = datetime.now().isoformat()
                return True
        return False
    
    def find_node(self, node_id: str) -> Optional['AccessibilityNode']:
        """Find node by ID recursively"""
        if self.id == node_id:
            return self
        
        for child in self.children:
            result = child.find_node(node_id)
            if result:
                return result
        
        return None
    
    def get_all_nodes(self) -> List['AccessibilityNode']:
        """Get all nodes in subtree"""
        nodes = [self]
        for child in self.children:
            nodes.extend(child.get_all_nodes())
        return nodes
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "type": self.type.value,
            "text": self.text,
            "alt_text": self.alt_text,
            "page": self.page,
            "bbox": self.bbox.to_list(),
            "status": self.status.value,
            "ai_confidence": self.ai_confidence,
            "ai_suggestion": self.ai_suggestion,
            "ai_generated": self.ai_generated,
            "pdf_techniques": self.pdf_techniques,
            "wcag_criteria": self.wcag_criteria,
            "user_modified": self.user_modified,
            "last_modified": self.last_modified,
            "children": [child.to_dict() for child in self.children]
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AccessibilityNode':
        """Create node from dictionary"""
        node = cls(
            id=data["id"],
            type=NodeType(data["type"]),
            page=data["page"],
            bbox=BoundingBox.from_list(data["bbox"]),
            status=NodeStatus(data.get("status", "ok")),
            text=data.get("text"),
            alt_text=data.get("alt_text"),
            ai_confidence=data.get("ai_confidence"),
            ai_suggestion=data.get("ai_suggestion"),
            ai_generated=data.get("ai_generated", False),
            pdf_techniques=data.get("pdf_techniques", []),
            wcag_criteria=data.get("wcag_criteria", []),
            user_modified=data.get("user_modified", False),
            last_modified=data.get("last_modified")
        )
        
        # Recursively create children
        for child_data in data.get("children", []):
            child = cls.from_dict(child_data)
            node.add_child(child)
        
        return node


@dataclass
class DocumentMetadata:
    """Document-level metadata"""
    title: str
    language: str = "en-US"
    pdfua_compliant: bool = False
    wcag_level: str = "AA"
    pages: int = 0
    created_date: Optional[str] = None
    modified_date: Optional[str] = None
    
    # AI processing info
    ai_enhanced: bool = False
    ai_model_used: Optional[str] = None
    processing_cost_usd: Optional[float] = None
    
    def __post_init__(self):
        if self.created_date is None:
            self.created_date = datetime.now().isoformat()
        if self.modified_date is None:
            self.modified_date = datetime.now().isoformat()


class AccessibilityTagTree:
    """Complete accessibility tag tree for a PDF document"""
    
    def __init__(self, metadata: DocumentMetadata, root: AccessibilityNode = None):
        self.metadata = metadata
        self.root = root or self._create_default_root()
        self.version = "1.0"
        self._node_cache = {}
        self._rebuild_cache()
    
    def _create_default_root(self) -> AccessibilityNode:
        """Create default document root node"""
        return AccessibilityNode(
            id="doc-root",
            type=NodeType.DOCUMENT,
            page=0,
            bbox=BoundingBox(0, 0, 0, 0),
            status=NodeStatus.OK,
            text=self.metadata.title
        )
    
    def _rebuild_cache(self):
        """Rebuild internal node cache for fast lookups"""
        self._node_cache = {}
        if self.root:
            for node in self.root.get_all_nodes():
                self._node_cache[node.id] = node
    
    def find_node(self, node_id: str) -> Optional[AccessibilityNode]:
        """Find node by ID using cache"""
        return self._node_cache.get(node_id)
    
    def add_node(self, parent_id: str, node: AccessibilityNode) -> bool:
        """Add node as child of parent"""
        parent = self.find_node(parent_id)
        if parent:
            parent.add_child(node)
            self._node_cache[node.id] = node
            self.metadata.modified_date = datetime.now().isoformat()
            return True
        return False
    
    def remove_node(self, node_id: str) -> bool:
        """Remove node and all its children"""
        node = self.find_node(node_id)
        if not node or node_id == "doc-root":
            return False
        
        # Find parent and remove from parent's children
        for parent in self._node_cache.values():
            if parent.remove_child(node_id):
                # Remove from cache
                nodes_to_remove = node.get_all_nodes()
                for n in nodes_to_remove:
                    self._node_cache.pop(n.id, None)
                
                self.metadata.modified_date = datetime.now().isoformat()
                return True
        
        return False
    
    def reorder_children(self, parent_id: str, child_order: List[str]) -> bool:
        """Reorder children of a parent node"""
        parent = self.find_node(parent_id)
        if not parent:
            return False
        
        # Create new ordered children list
        new_children = []
        child_dict = {child.id: child for child in parent.children}
        
        for child_id in child_order:
            if child_id in child_dict:
                new_children.append(child_dict[child_id])
        
        # Add any children not in the order list
        for child in parent.children:
            if child.id not in child_order:
                new_children.append(child)
        
        parent.children = new_children
        parent.last_modified = datetime.now().isoformat()
        self.metadata.modified_date = datetime.now().isoformat()
        return True
    
    def update_node(self, node_id: str, **kwargs) -> bool:
        """Update node properties"""
        node = self.find_node(node_id)
        if not node:
            return False
        
        # Update allowed properties
        allowed_updates = ['text', 'alt_text', 'type', 'status', 'ai_confidence', 
                          'ai_suggestion', 'pdf_techniques', 'wcag_criteria']
        
        updated = False
        for key, value in kwargs.items():
            if key in allowed_updates and hasattr(node, key):
                if key == 'type' and isinstance(value, str):
                    value = NodeType(value)
                elif key == 'status' and isinstance(value, str):
                    value = NodeStatus(value)
                
                setattr(node, key, value)
                updated = True
        
        if updated:
            node.user_modified = True
            node.last_modified = datetime.now().isoformat()
            self.metadata.modified_date = datetime.now().isoformat()
        
        return updated
    
    def get_nodes_by_status(self, status: NodeStatus) -> List[AccessibilityNode]:
        """Get all nodes with specific status"""
        return [node for node in self._node_cache.values() if node.status == status]
    
    def get_nodes_by_type(self, node_type: NodeType) -> List[AccessibilityNode]:
        """Get all nodes of specific type"""
        return [node for node in self._node_cache.values() if node.type == node_type]
    
    def get_nodes_by_page(self, page_num: int) -> List[AccessibilityNode]:
        """Get all nodes on specific page"""
        return [node for node in self._node_cache.values() if node.page == page_num]
    
    def get_ai_generated_nodes(self) -> List[AccessibilityNode]:
        """Get all AI-generated nodes"""
        return [node for node in self._node_cache.values() if node.ai_generated]
    
    def get_nodes_needing_review(self) -> List[AccessibilityNode]:
        """Get nodes that need manual review"""
        return [node for node in self._node_cache.values() 
                if node.status in [NodeStatus.AI_SUGGESTED, NodeStatus.MANUAL_REVIEW, NodeStatus.ERROR]]
    
    def validate_structure(self) -> Dict[str, Any]:
        """Validate tag tree structure and return issues"""
        issues = []
        warnings = []
        
        # Check for orphaned nodes (nodes with no path to root)
        reachable_nodes = set()
        if self.root:
            reachable_nodes = {node.id for node in self.root.get_all_nodes()}
        
        orphaned = set(self._node_cache.keys()) - reachable_nodes
        if orphaned:
            issues.append(f"Orphaned nodes found: {list(orphaned)}")
        
        # Check heading hierarchy
        headings = self.get_nodes_by_type(NodeType.H1) + \
                  self.get_nodes_by_type(NodeType.H2) + \
                  self.get_nodes_by_type(NodeType.H3) + \
                  self.get_nodes_by_type(NodeType.H4) + \
                  self.get_nodes_by_type(NodeType.H5) + \
                  self.get_nodes_by_type(NodeType.H6)
        
        # Sort by page and position
        headings.sort(key=lambda h: (h.page, -h.bbox.y0, h.bbox.x0))
        
        prev_level = 0
        for heading in headings:
            level = int(heading.type.value[1])  # Extract number from H1, H2, etc.
            if level - prev_level > 1:
                warnings.append(f"Heading hierarchy skip: {heading.type.value} after H{prev_level} on page {heading.page}")
            prev_level = level
        
        # Check for images without alt text
        figures = self.get_nodes_by_type(NodeType.FIGURE)
        for figure in figures:
            if not figure.alt_text or not figure.alt_text.strip():
                issues.append(f"Figure without alt text on page {figure.page}")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "stats": {
                "total_nodes": len(self._node_cache),
                "ai_generated": len(self.get_ai_generated_nodes()),
                "needs_review": len(self.get_nodes_needing_review()),
                "figures_without_alt": len([f for f in figures if not f.alt_text])
            }
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Export to JSON string"""
        data = {
            "document": {
                "title": self.metadata.title,
                "language": self.metadata.language,
                "metadata": {
                    "pdfua_compliant": self.metadata.pdfua_compliant,
                    "wcag_level": self.metadata.wcag_level,
                    "pages": self.metadata.pages,
                    "created_date": self.metadata.created_date,
                    "modified_date": self.metadata.modified_date,
                    "ai_enhanced": self.metadata.ai_enhanced,
                    "ai_model_used": self.metadata.ai_model_used,
                    "processing_cost_usd": self.metadata.processing_cost_usd
                },
                "children": [child.to_dict() for child in self.root.children] if self.root else []
            },
            "version": self.version,
            "validation": self.validate_structure()
        }
        
        return json.dumps(data, indent=indent, ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'AccessibilityTagTree':
        """Import from JSON string"""
        try:
            data = json.loads(json_str)
            document_data = data["document"]
            
            # Create metadata
            metadata = DocumentMetadata(
                title=document_data["title"],
                language=document_data.get("language", "en-US"),
                pdfua_compliant=document_data["metadata"].get("pdfua_compliant", False),
                wcag_level=document_data["metadata"].get("wcag_level", "AA"),
                pages=document_data["metadata"].get("pages", 0),
                created_date=document_data["metadata"].get("created_date"),
                modified_date=document_data["metadata"].get("modified_date"),
                ai_enhanced=document_data["metadata"].get("ai_enhanced", False),
                ai_model_used=document_data["metadata"].get("ai_model_used"),
                processing_cost_usd=document_data["metadata"].get("processing_cost_usd")
            )
            
            # Create tree instance
            tree = cls(metadata)
            
            # Add children to root
            for child_data in document_data.get("children", []):
                child_node = AccessibilityNode.from_dict(child_data)
                tree.root.add_child(child_node)
            
            # Rebuild cache
            tree._rebuild_cache()
            
            return tree
            
        except Exception as e:
            logger.error(f"Failed to parse JSON tag tree: {e}")
            raise ValueError(f"Invalid tag tree JSON: {e}")
    
    def to_file(self, file_path: str):
        """Save to JSON file"""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(self.to_json())
        logger.info(f"Saved tag tree to {file_path}")
    
    @classmethod
    def from_file(cls, file_path: str) -> 'AccessibilityTagTree':
        """Load from JSON file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return cls.from_json(f.read())
    
    def export_for_frontend(self) -> Dict:
        """Export in format optimized for frontend display"""
        def node_to_frontend(node: AccessibilityNode) -> Dict:
            return {
                "id": node.id,
                "type": node.type.value,
                "text": node.text,
                "altText": node.alt_text,
                "page": node.page,
                "bbox": node.bbox.to_list(),
                "status": node.status.value,
                "aiGenerated": node.ai_generated,
                "aiConfidence": node.ai_confidence,
                "needsReview": node.status in [NodeStatus.AI_SUGGESTED, NodeStatus.MANUAL_REVIEW],
                "children": [node_to_frontend(child) for child in node.children]
            }
        
        return {
            "title": self.metadata.title,
            "language": self.metadata.language,
            "pages": self.metadata.pages,
            "aiEnhanced": self.metadata.ai_enhanced,
            "tree": [node_to_frontend(child) for child in self.root.children] if self.root else [],
            "stats": self.validate_structure()["stats"]
        }


class TagTreeBuilder:
    """Helper class to build tag trees from PDF analysis data"""
    
    @staticmethod
    def from_pdf_analysis(analysis: Dict, document_title: str = "") -> AccessibilityTagTree:
        """Build tag tree from PDF parser analysis results"""
        
        # Create document metadata
        metadata = DocumentMetadata(
            title=document_title or analysis.get("metadata", {}).get("title", "Untitled Document"),
            language=analysis.get("document_language", "en-US"),
            pages=analysis.get("total_pages", 0),
            pdfua_compliant=False,  # Will be determined after processing
            wcag_level="AA"
        )
        
        # Create tag tree
        tree = AccessibilityTagTree(metadata)
        
        # Process reading order elements
        reading_order = analysis.get("reading_order", [])
        
        for element in reading_order:
            node_id = f"{element.type}_{element.page_num}_{len(tree._node_cache)}"
            
            # Determine node type
            if element.type == "heading":
                heading_level = element.metadata.get("heading_level", 1)
                node_type = NodeType(f"H{heading_level}")
            elif element.type == "text":
                node_type = NodeType.P
            elif element.type == "table":
                node_type = NodeType.TABLE
            else:
                node_type = NodeType.P  # Default fallback
            
            # Create node
            node = AccessibilityNode(
                id=node_id,
                type=node_type,
                page=element.page_num,
                bbox=BoundingBox.from_list(list(element.bbox)),
                text=element.content[:100],  # Truncate long text
                status=NodeStatus.OK
            )
            
            tree.add_node("doc-root", node)
        
        # Add images as Figure nodes
        for image in analysis.get("images", []):
            node_id = f"img_{image.page_num}_{image.image_id}"
            
            node = AccessibilityNode(
                id=node_id,
                type=NodeType.FIGURE,
                page=image.page_num,
                bbox=BoundingBox.from_list(list(image.bbox)),
                alt_text=image.alt_text,
                status=NodeStatus.OK if image.alt_text else NodeStatus.MANUAL_REVIEW
            )
            
            tree.add_node("doc-root", node)
        
        # Add tables with structure
        for table in analysis.get("tables", []):
            table_node_id = f"table_{table.page_num}_{table.metadata.get('table_id', 0)}"
            
            table_node = AccessibilityNode(
                id=table_node_id,
                type=NodeType.TABLE,
                page=table.page_num,
                bbox=BoundingBox.from_list(list(table.bbox)),
                status=NodeStatus.OK
            )
            
            tree.add_node("doc-root", table_node)
            
            # Add table rows and cells
            table_data = table.metadata.get("data", [])
            for row_idx, row_data in enumerate(table_data[:5]):  # Limit for performance
                row_node_id = f"{table_node_id}_row_{row_idx}"
                row_node = AccessibilityNode(
                    id=row_node_id,
                    type=NodeType.TR,
                    page=table.page_num,
                    bbox=table_node.bbox,  # Use table bbox for rows
                    status=NodeStatus.OK
                )
                
                tree.add_node(table_node_id, row_node)
                
                # Add cells
                cell_type = NodeType.TH if row_idx == 0 else NodeType.TD
                for cell_idx, cell_data in enumerate(row_data[:6]):  # Limit columns
                    cell_node_id = f"{row_node_id}_cell_{cell_idx}"
                    cell_node = AccessibilityNode(
                        id=cell_node_id,
                        type=cell_type,
                        page=table.page_num,
                        bbox=table_node.bbox,
                        text=str(cell_data)[:50],  # Truncate cell text
                        status=NodeStatus.OK
                    )
                    
                    tree.add_node(row_node_id, cell_node)
        
        logger.info(f"Built tag tree with {len(tree._node_cache)} nodes")
        return tree