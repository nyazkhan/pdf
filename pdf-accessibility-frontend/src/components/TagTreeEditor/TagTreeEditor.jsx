import React, { useState } from 'react';
import { SimpleTreeView } from '@mui/x-tree-view/SimpleTreeView';
import { TreeItem } from '@mui/x-tree-view/TreeItem';
import {
  Box,
  Paper,
  Typography,
  IconButton,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  Tooltip,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import {
  ExpandMore,
  ChevronRight,
  Edit,
  Delete,
  Add,
  Warning,
  CheckCircle,
  AutoFixHigh,
  Error,
} from '@mui/icons-material';

const NODE_TYPES = [
  'Document',
  'H1', 'H2', 'H3', 'H4', 'H5', 'H6',
  'P',
  'Figure',
  'Table',
  'TR', 'TD', 'TH',
  'List',
  'LI',
  'Link',
  'Span',
  'Div',
];

const getStatusIcon = (status) => {
  switch (status) {
    case 'ok':
      return <CheckCircle color="success" fontSize="small" />;
    case 'ai-suggested':
      return <AutoFixHigh color="info" fontSize="small" />;
    case 'manual-review':
      return <Warning color="warning" fontSize="small" />;
    case 'error':
      return <Error color="error" fontSize="small" />;
    default:
      return null;
  }
};

const getStatusColor = (status) => {
  switch (status) {
    case 'ok':
      return 'success';
    case 'ai-suggested':
      return 'info';
    case 'manual-review':
      return 'warning';
    case 'error':
      return 'error';
    default:
      return 'default';
  }
};

const TagTreeEditor = ({
  tagTree,
  onNodeSelect,
  onNodeEdit,
  onNodeDelete,
  onApplyAISuggestion,
}) => {
  const [expanded, setExpanded] = useState(['root']);
  const [selected, setSelected] = useState('');
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editingNode, setEditingNode] = useState(null);
  const [editForm, setEditForm] = useState({
    type: '',
    text: '',
    alt_text: '',
  });

  const handleToggle = (event, nodeIds) => {
    setExpanded(nodeIds);
  };

  const handleSelect = (event, nodeId) => {
    if (nodeId) {
      setSelected(nodeId);
      const node = findNodeById(tagTree, nodeId);
      if (node && onNodeSelect) {
        onNodeSelect(node);
      }
    }
  };

  const findNodeById = (node, id) => {
    if (node.id === id) return node;
    if (node.children) {
      for (const child of node.children) {
        const found = findNodeById(child, id);
        if (found) return found;
      }
    }
    return null;
  };

  const handleEditClick = (node) => {
    setEditingNode(node);
    setEditForm({
      type: node.type,
      text: node.text || '',
      alt_text: node.alt_text || '',
    });
    setEditDialogOpen(true);
  };

  const handleEditSave = () => {
    if (editingNode && onNodeEdit) {
      const updatedNode = {
        ...editingNode,
        ...editForm,
        status: 'manual-review',
      };
      onNodeEdit(updatedNode);
    }
    setEditDialogOpen(false);
  };

  const renderTreeNodes = (node, depth = 0, visitedIds = new Set()) => {
    // Prevent infinite recursion with depth limit
    if (depth > 20) {
      console.warn('Maximum tree depth reached, stopping recursion');
      return (
        <TreeItem key={node.id} itemId={node.id} label="[Max depth reached]" />
      );
    }

    // Prevent circular references
    if (visitedIds.has(node.id)) {
      console.warn(`Circular reference detected for node ${node.id}`);
      return (
        <TreeItem key={node.id} itemId={node.id} label="[Circular reference]" />
      );
    }
    
    const newVisitedIds = new Set(visitedIds);
    newVisitedIds.add(node.id);

    const nodeLabel = (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 0.5 }}>
        {getStatusIcon(node.status)}
        <Typography variant="body2" component="span">
          <strong>{node.type}</strong>
          {node.text && `: ${node.text.substring(0, 50)}${node.text.length > 50 ? '...' : ''}`}
        </Typography>
        {node.ai_suggestion && (
          <Tooltip title={`AI Suggestion: ${node.ai_suggestion}`}>
            <Chip
              label="AI"
              size="small"
              color="info"
              onClick={(e) => {
                e.stopPropagation();
                if (onApplyAISuggestion) {
                  onApplyAISuggestion(node.id);
                }
              }}
            />
          </Tooltip>
        )}
        <Chip
          label={`Page ${node.page}`}
          size="small"
          variant="outlined"
        />
        {node.status !== 'ok' && (
          <Chip
            label={node.status}
            size="small"
            color={getStatusColor(node.status)}
            variant="outlined"
          />
        )}
        <Box sx={{ ml: 'auto' }}>
          <IconButton
            size="small"
            onClick={(e) => {
              e.stopPropagation();
              handleEditClick(node);
            }}
          >
            <Edit fontSize="small" />
          </IconButton>
          {onNodeDelete && (
            <IconButton
              size="small"
              onClick={(e) => {
                e.stopPropagation();
                onNodeDelete(node.id);
              }}
            >
              <Delete fontSize="small" />
            </IconButton>
          )}
        </Box>
      </Box>
    );

    return (
      <TreeItem key={node.id} itemId={node.id} label={nodeLabel}>
        {node.children?.map(child => renderTreeNodes(child, depth + 1, newVisitedIds))}
      </TreeItem>
    );
  };

  return (
    <>
      <Paper elevation={3} sx={{ p: 2, height: '100%', overflow: 'auto' }}>
        <Typography variant="h6" gutterBottom>
          Accessibility Tag Tree
        </Typography>
        
        <Box sx={{ mb: 2 }}>
          <Typography variant="body2" color="text.secondary">
            Legend:
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 1 }}>
            <Chip icon={<CheckCircle />} label="OK" size="small" color="success" />
            <Chip icon={<AutoFixHigh />} label="AI Suggested" size="small" color="info" />
            <Chip icon={<Warning />} label="Manual Review" size="small" color="warning" />
            <Chip icon={<Error />} label="Error" size="small" color="error" />
          </Box>
        </Box>

        <SimpleTreeView
          aria-label="accessibility tag tree"
          slots={{
            collapseIcon: ExpandMore,
            expandIcon: ChevronRight,
          }}
          expandedItems={expanded}
          selectedItems={selected}
          onExpandedItemsChange={handleToggle}
          onSelectedItemsChange={handleSelect}
          sx={{ flexGrow: 1, maxWidth: '100%', overflowY: 'auto' }}
        >
          {renderTreeNodes(tagTree)}
        </SimpleTreeView>
      </Paper>

      <Dialog open={editDialogOpen} onClose={() => setEditDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Edit Node</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
            <FormControl fullWidth>
              <InputLabel>Node Type</InputLabel>
              <Select
                value={editForm.type}
                label="Node Type"
                onChange={(e) => setEditForm({ ...editForm, type: e.target.value })}
              >
                {NODE_TYPES.map(type => (
                  <MenuItem key={type} value={type}>{type}</MenuItem>
                ))}
              </Select>
            </FormControl>

            <TextField
              fullWidth
              label="Text Content"
              value={editForm.text}
              onChange={(e) => setEditForm({ ...editForm, text: e.target.value })}
              multiline
              rows={3}
            />

            {editingNode?.type === 'Figure' && (
              <TextField
                fullWidth
                label="Alt Text"
                value={editForm.alt_text}
                onChange={(e) => setEditForm({ ...editForm, alt_text: e.target.value })}
                multiline
                rows={2}
              />
            )}

            {editingNode?.ai_suggestion && (
              <Paper sx={{ p: 2, bgcolor: 'info.light' }}>
                <Typography variant="body2" gutterBottom>
                  <strong>AI Suggestion:</strong>
                </Typography>
                <Typography variant="body2">
                  {editingNode.ai_suggestion}
                </Typography>
                <Button
                  startIcon={<AutoFixHigh />}
                  onClick={() => {
                    if (editingNode.type === 'Figure' && editingNode.ai_suggestion) {
                      setEditForm({ ...editForm, alt_text: editingNode.ai_suggestion });
                    }
                  }}
                  sx={{ mt: 1 }}
                >
                  Apply Suggestion
                </Button>
              </Paper>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleEditSave} variant="contained">Save</Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default TagTreeEditor;