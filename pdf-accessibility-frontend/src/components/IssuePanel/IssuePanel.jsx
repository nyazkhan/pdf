import React, { useState } from 'react';
import {
  Paper,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  ListItemSecondaryAction,
  Typography,
  Chip,
  IconButton,
  Button,
  Box,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Checkbox,
  FormControlLabel,
  LinearProgress,
  Alert,
  Tooltip,
} from '@mui/material';
import {
  ExpandMore,
  Error,
  Warning,
  Info,
  CheckCircle,
  Build,
  AutoFixHigh,
  Visibility,
  CheckBox,
  CheckBoxOutlineBlank,
} from '@mui/icons-material';

const getSeverityIcon = (severity) => {
  switch (severity) {
    case 'error':
      return <Error color="error" />;
    case 'warning':
      return <Warning color="warning" />;
    case 'info':
      return <Info color="info" />;
    default:
      return null;
  }
};

const getSeverityColor = (severity) => {
  switch (severity) {
    case 'error':
      return 'error';
    case 'warning':
      return 'warning';
    case 'info':
      return 'info';
    default:
      return 'success';
  }
};

const IssuePanel = ({
  issues,
  onIssueFix,
  onIssueSelect,
  onBatchFix,
  onRequestAISuggestion,
  fixProgress,
}) => {
  const [selectedIssues, setSelectedIssues] = useState(new Set());
  const [expandedCategories, setExpandedCategories] = useState(new Set(['error']));

  // Group issues by severity
  const groupedIssues = issues.reduce((acc, issue) => {
    if (!acc[issue.severity]) {
      acc[issue.severity] = [];
    }
    acc[issue.severity].push(issue);
    return acc;
  }, {});

  const handleSelectIssue = (issueId) => {
    const newSelected = new Set(selectedIssues);
    if (newSelected.has(issueId)) {
      newSelected.delete(issueId);
    } else {
      newSelected.add(issueId);
    }
    setSelectedIssues(newSelected);
  };

  const handleSelectAll = (severity) => {
    const severityIssues = groupedIssues[severity] || [];
    const allSelected = severityIssues.every(issue => selectedIssues.has(issue.id));
    
    const newSelected = new Set(selectedIssues);
    severityIssues.forEach(issue => {
      if (allSelected) {
        newSelected.delete(issue.id);
      } else {
        newSelected.add(issue.id);
      }
    });
    setSelectedIssues(newSelected);
  };

  const handleBatchFix = () => {
    if (onBatchFix && selectedIssues.size > 0) {
      onBatchFix(Array.from(selectedIssues));
    }
  };

  const autoFixableCount = issues.filter(i => i.auto_fixable).length;
  const manualReviewCount = issues.filter(i => i.manual_review_required).length;

  return (
    <Paper elevation={3} sx={{ p: 2, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Typography variant="h6" gutterBottom>
        Accessibility Issues
      </Typography>

      <Box sx={{ mb: 2 }}>
        <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
          <Chip
            icon={<Error />}
            label={`${groupedIssues.error?.length || 0} Errors`}
            color="error"
            size="small"
          />
          <Chip
            icon={<Warning />}
            label={`${groupedIssues.warning?.length || 0} Warnings`}
            color="warning"
            size="small"
          />
          <Chip
            icon={<Info />}
            label={`${groupedIssues.info?.length || 0} Info`}
            color="info"
            size="small"
          />
        </Box>
        
        {autoFixableCount > 0 && (
          <Alert severity="success" sx={{ mb: 1 }}>
            {autoFixableCount} issues can be auto-fixed
          </Alert>
        )}
        
        {manualReviewCount > 0 && (
          <Alert severity="warning" sx={{ mb: 1 }}>
            {manualReviewCount} issues require manual review
          </Alert>
        )}
      </Box>

      {selectedIssues.size > 0 && (
        <Box sx={{ mb: 2 }}>
          <Button
            variant="contained"
            startIcon={<Build />}
            onClick={handleBatchFix}
            fullWidth
          >
            Fix {selectedIssues.size} Selected Issues
          </Button>
        </Box>
      )}

      {fixProgress !== undefined && fixProgress > 0 && (
        <Box sx={{ mb: 2 }}>
          <Typography variant="body2" gutterBottom>
            Applying fixes...
          </Typography>
          <LinearProgress variant="determinate" value={fixProgress} />
        </Box>
      )}

      <Box sx={{ flexGrow: 1, overflow: 'auto' }}>
        {Object.entries(groupedIssues).map(([severity, severityIssues]) => (
          <Accordion
            key={severity}
            expanded={expandedCategories.has(severity)}
            onChange={(_, expanded) => {
              const newExpanded = new Set(expandedCategories);
              if (expanded) {
                newExpanded.add(severity);
              } else {
                newExpanded.delete(severity);
              }
              setExpandedCategories(newExpanded);
            }}
          >
            <AccordionSummary expandIcon={<ExpandMore />}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
                {getSeverityIcon(severity)}
                <Typography sx={{ flexGrow: 1 }}>
                  {severity.charAt(0).toUpperCase() + severity.slice(1)} ({severityIssues.length})
                </Typography>
                <IconButton
                  size="small"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleSelectAll(severity);
                  }}
                >
                  {severityIssues.every(i => selectedIssues.has(i.id)) ? 
                    <CheckBox /> : <CheckBoxOutlineBlank />}
                </IconButton>
              </Box>
            </AccordionSummary>
            <AccordionDetails>
              <List dense>
                {severityIssues.map((issue) => (
                  <ListItem
                    key={issue.id}
                    onClick={() => onIssueSelect && onIssueSelect(issue)}
                    sx={{
                      borderRadius: 1,
                      mb: 1,
                      bgcolor: selectedIssues.has(issue.id) ? 'action.selected' : 'background.paper',
                      '&:hover': {
                        bgcolor: 'action.hover',
                      },
                    }}
                  >
                    <ListItemIcon>
                      <Checkbox
                        checked={selectedIssues.has(issue.id)}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSelectIssue(issue.id);
                        }}
                      />
                    </ListItemIcon>
                    <ListItemText
                      primary={
                        <Box>
                          <Typography variant="body2" component="span">
                            {issue.type}
                          </Typography>
                          <Chip
                            label={`Page ${issue.page}`}
                            size="small"
                            sx={{ ml: 1 }}
                          />
                          {issue.wcag_criteria && (
                            <Chip
                              label={issue.wcag_criteria}
                              size="small"
                              variant="outlined"
                              sx={{ ml: 0.5 }}
                            />
                          )}
                        </Box>
                      }
                      secondary={
                        <Box>
                          <Typography variant="body2" color="text.secondary">
                            {issue.description}
                          </Typography>
                          {issue.ai_suggestion && (
                            <Chip
                              icon={<AutoFixHigh />}
                              label="AI suggestion available"
                              size="small"
                              color="info"
                              sx={{ mt: 0.5 }}
                            />
                          )}
                        </Box>
                      }
                    />
                    <ListItemSecondaryAction>
                      <Box sx={{ display: 'flex', gap: 0.5 }}>
                        {issue.ai_suggestion && onRequestAISuggestion && (
                          <Tooltip title="Apply AI Suggestion">
                            <IconButton
                              size="small"
                              onClick={(e) => {
                                e.stopPropagation();
                                onRequestAISuggestion(issue.id);
                              }}
                            >
                              <AutoFixHigh />
                            </IconButton>
                          </Tooltip>
                        )}
                        {issue.fix_available && onIssueFix && (
                          <Tooltip title="Fix Issue">
                            <IconButton
                              size="small"
                              onClick={(e) => {
                                e.stopPropagation();
                                onIssueFix(issue.id);
                              }}
                            >
                              <Build />
                            </IconButton>
                          </Tooltip>
                        )}
                        <Tooltip title="View in PDF">
                          <IconButton
                            size="small"
                            onClick={(e) => {
                              e.stopPropagation();
                              onIssueSelect && onIssueSelect(issue);
                            }}
                          >
                            <Visibility />
                          </IconButton>
                        </Tooltip>
                      </Box>
                    </ListItemSecondaryAction>
                  </ListItem>
                ))}
              </List>
            </AccordionDetails>
          </Accordion>
        ))}
      </Box>
    </Paper>
  );
};

export default IssuePanel;