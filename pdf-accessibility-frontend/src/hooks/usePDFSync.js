import { useState, useCallback } from 'react';

export const usePDFSync = () => {
  const [highlights, setHighlights] = useState([]);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [selectedIssueId, setSelectedIssueId] = useState(null);
  const [scrollTarget, setScrollTarget] = useState(null);

  // Handle tree node selection
  const handleNodeSelect = useCallback((node) => {
    setSelectedNodeId(node.id);
    setSelectedIssueId(null);

    // Create highlight for the node
    if (node.bbox && node.page) {
      const highlight = {
        page: node.page,
        x: node.bbox.x,
        y: node.bbox.y,
        width: node.bbox.width,
        height: node.bbox.height,
        color: 'rgba(0, 123, 255, 0.3)',
        id: node.id,
        type: 'node'
      };

      setHighlights([highlight]);
      setScrollTarget({ page: node.page, bbox: node.bbox });
    }
  }, []);

  // Handle issue selection
  const handleIssueSelect = useCallback((issue) => {
    setSelectedIssueId(issue.id);
    setSelectedNodeId(null);

    // Create highlight for the issue
    if (issue.element?.bbox && issue.page) {
      const highlight = {
        page: issue.page,
        x: issue.element.bbox.x,
        y: issue.element.bbox.y,
        width: issue.element.bbox.width,
        height: issue.element.bbox.height,
        color: 'rgba(255, 0, 0, 0.3)',
        id: issue.id,
        type: 'issue'
      };

      setHighlights([highlight]);
      setScrollTarget({ page: issue.page, bbox: issue.element.bbox });
    }
  }, []);

  // Handle multiple node selection
  const handleMultiNodeSelect = useCallback((nodes) => {
    const newHighlights = nodes
      .filter(node => node.bbox && node.page)
      .map(node => ({
        page: node.page,
        x: node.bbox.x,
        y: node.bbox.y,
        width: node.bbox.width,
        height: node.bbox.height,
        color: 'rgba(0, 123, 255, 0.3)',
        id: node.id,
        type: 'node'
      }));

    setHighlights(newHighlights);
  }, []);

  // Handle PDF element click
  const handlePDFElementClick = useCallback((elementId, pageNum, bbox) => {
    // This will be used to select the corresponding node in the tree
    return { elementId, pageNum, bbox };
  }, []);

  // Clear all highlights
  const clearHighlights = useCallback(() => {
    setHighlights([]);
    setSelectedNodeId(null);
    setSelectedIssueId(null);
    setScrollTarget(null);
  }, []);

  // Find node by position in PDF
  const findNodeByPosition = useCallback((pageNum, x, y, tree) => {
    const checkNode = (node) => {
      if (node.page === pageNum && node.bbox) {
        const { bbox } = node;
        if (x >= bbox.x && x <= bbox.x + bbox.width &&
            y >= bbox.y && y <= bbox.y + bbox.height) {
          return node;
        }
      }

      if (node.children) {
        for (const child of node.children) {
          const found = checkNode(child);
          if (found) return found;
        }
      }

      return null;
    };

    return checkNode(tree);
  }, []);

  return {
    highlights,
    selectedNodeId,
    selectedIssueId,
    scrollTarget,
    handleNodeSelect,
    handleIssueSelect,
    handleMultiNodeSelect,
    handlePDFElementClick,
    clearHighlights,
    findNodeByPosition
  };
};