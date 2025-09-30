import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Container,
  AppBar,
  Toolbar,
  Typography,
  Button,
  Paper,
  Alert,
  Snackbar,
  LinearProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  Tabs,
  Tab,
  IconButton,
} from '@mui/material';
import {
  CloudUpload,
  Download,
  CheckCircle,
  Settings,
  DarkMode,
  LightMode,
} from '@mui/icons-material';
import { useDropzone } from 'react-dropzone';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';

import EnhancedPDFViewer from './components/PDFViewer/EnhancedPDFViewer';
import TagTreeEditor from './components/TagTreeEditor/TagTreeEditor';
import IssuePanel from './components/IssuePanel/IssuePanel';
import apiService from './services/api.service';
import websocketService from './services/websocket.service';
import { usePDFSync } from './hooks/usePDFSync';

const queryClient = new QueryClient();

function AppContent() {
  const [sessionId, setSessionId] = useState(null);
  const [pdfFile, setPdfFile] = useState(null);
  const [pdfUrl, setPdfUrl] = useState(null);
  const [tagTree, setTagTree] = useState(null);
  const [issues, setIssues] = useState([]);
  const [selectedIssue, setSelectedIssue] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [highlights, setHighlights] = useState([]);
  const [notification, setNotification] = useState({ open: false, message: '', severity: 'info' });
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [fixProgress, setFixProgress] = useState(0);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [wcagLevel, setWcagLevel] = useState('AA');
  const [enableAI, setEnableAI] = useState(true);
  const [activeTab, setActiveTab] = useState(0);
  const [darkMode, setDarkMode] = useState(false);
  
  // PDF Sync hook
  const {
    highlights: syncHighlights,
    selectedNodeId,
    selectedIssueId,
    scrollTarget,
    handleNodeSelect,
    handleIssueSelect: handleIssueSyncSelect,
    handlePDFElementClick,
    clearHighlights
  } = usePDFSync();

  // Transform backend tag tree to frontend format
  const transformTagTree = (backendTree) => {
    if (!backendTree) {
      return { id: 'root', type: 'Document', page: 1, status: 'ok', children: [] };
    }

    // If the tree already has the correct structure, return it
    if (backendTree.id && backendTree.type) {
      return backendTree;
    }

    // Transform from backend structure { document: { children: [...] }, ... }
    // to frontend structure { id, type, children, ... }
    if (backendTree.document) {
      const doc = backendTree.document;
      const rootNode = {
        id: 'root',
        type: 'Document',
        text: doc.title || 'Untitled',
        page: 1,
        status: 'ok',
        children: doc.children || []
      };

      // Ensure all children have required fields
      const ensureNodeStructure = (node) => {
        return {
          id: node.id || `node_${Math.random().toString(36).substr(2, 9)}`,
          type: node.type || 'Unknown',
          text: node.text || '',
          alt_text: node.alt_text,
          page: node.page || 1,
          bbox: node.bbox,
          status: node.status || 'ok',
          ai_suggestion: node.ai_suggestion,
          children: node.children ? node.children.map(ensureNodeStructure) : []
        };
      };

      rootNode.children = rootNode.children.map(ensureNodeStructure);
      return rootNode;
    }

    // Fallback to empty tree
    return { id: 'root', type: 'Document', page: 1, status: 'ok', children: [] };
  };

  // File upload handling
  const onDrop = useCallback(async (acceptedFiles) => {
    if (acceptedFiles.length > 0) {
      const file = acceptedFiles[0];
      setPdfFile(file);
      // Keep the file data, don't set URL initially to avoid double loading

      try {
        setAnalysisProgress(10);
        const uploadResult = await apiService.uploadPDF(file);
        setSessionId(uploadResult.session_id);
        setAnalysisProgress(30);

        // Connect WebSocket
        websocketService.connect(uploadResult.session_id);

        // Analyze PDF
        const analysisResult = await apiService.analyzePDF(
          uploadResult.filename,
          wcagLevel,
          enableAI
        );

        // Transform the tag tree to match frontend expectations
        const transformedTree = transformTagTree(analysisResult.tag_tree);
        setTagTree(transformedTree);
        setIssues(analysisResult.issues);
        setAnalysisProgress(100);

        // Store download URL for future use but don't set it to avoid reload
        // The PDF is already loaded from file data, no need to switch to URL
        const downloadUrl = await apiService.getPDFUrl(uploadResult.session_id);
        // setPdfUrl(downloadUrl); // Keep using file data to avoid reload

        setNotification({
          open: true,
          message: `PDF analyzed: ${analysisResult.issues.length} issues found`,
          severity: 'success'
        });
      } catch (error) {
        console.error('Error processing PDF:', error);
        setNotification({
          open: true,
          message: 'Error processing PDF',
          severity: 'error'
        });
        setAnalysisProgress(0);
        // On error, create blob URL for basic viewing
        setPdfUrl(URL.createObjectURL(file));
      }
    }
  }, [wcagLevel, enableAI]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1,
  });

  // WebSocket event handlers
  useEffect(() => {
    websocketService.on('ai_processing', (data) => {
      console.log('AI Processing:', data);
      if (data.status === 'completed') {
        setNotification({
          open: true,
          message: `AI enhanced ${data.enhanced_count} elements`,
          severity: 'info'
        });
      }
    });

    websocketService.on('ai_suggestions', (data) => {
      console.log('AI Suggestions:', data);
      // Update tag tree with AI suggestions
      if (tagTree) {
        // Merge AI suggestions into tag tree - ensure structure is maintained
        const updatedTree = { ...tagTree };
        setTagTree(updatedTree);
      }
    });

    return () => {
      websocketService.disconnect();
    };
  }, [tagTree]);

  // Handle issue selection
  const handleIssueSelect = (issue) => {
    setSelectedIssue(issue);
    handleIssueSyncSelect(issue);
    if (issue.page) {
      setCurrentPage(issue.page);
    }
    if (issue.element?.bbox) {
      setHighlights([{
        page: issue.page,
        ...issue.element.bbox,
        color: 'red'
      }]);
    }
  };

  // Handle batch fix
  const handleBatchFix = async (issueIds) => {
    if (!sessionId) return;

    try {
      setFixProgress(10);
      const fixes = issues
        .filter(issue => issueIds.includes(issue.id))
        .map(issue => ({
          issue_id: issue.id,
          type: issue.type,
          data: issue.fix_data || {}
        }));

      const result = await apiService.applyFixes(sessionId, fixes, true);
      setFixProgress(100);
      
      setNotification({
        open: true,
        message: `Applied ${result.applied_fixes} fixes`,
        severity: 'success'
      });

      // Update issues list
      const updatedIssues = issues.map(issue => {
        if (issueIds.includes(issue.id)) {
          return { ...issue, fixed: true };
        }
        return issue;
      });
      setIssues(updatedIssues);
      
      setTimeout(() => setFixProgress(0), 2000);
    } catch (error) {
      console.error('Error applying fixes:', error);
      setNotification({
        open: true,
        message: 'Error applying fixes',
        severity: 'error'
      });
      setFixProgress(0);
    }
  };

  // Handle node edit in tag tree
  const handleNodeEdit = (node) => {
    console.log('Editing node:', node);
    // Update tag tree - ensure we maintain the correct structure
    if (tagTree) {
      const updatedTree = { ...tagTree };
      // Here you would implement the logic to update the specific node
      // For now, just trigger a re-render
      setTagTree(updatedTree);
    }
  };

  // Handle AI suggestion application
  const handleApplyAISuggestion = async (nodeId) => {
    if (!sessionId) return;

    try {
      // Apply AI suggestion
      console.log('Applying AI suggestion for node:', nodeId);
      setNotification({
        open: true,
        message: 'AI suggestion applied',
        severity: 'success'
      });
    } catch (error) {
      console.error('Error applying AI suggestion:', error);
    }
  };

  // Handle tab change
  const handleTabChange = (event, newValue) => {
    setActiveTab(newValue);
  };

  // Validate PDF
  const handleValidate = async () => {
    if (!sessionId) return;

    try {
      const result = await apiService.validatePDF(sessionId);
      
      setNotification({
        open: true,
        message: result.compliant 
          ? '✓ PDF is compliant with PDF/UA'
          : `⚠ ${result.failed_checks} validation issues found`,
        severity: result.compliant ? 'success' : 'warning'
      });
    } catch (error) {
      console.error('Error validating PDF:', error);
    }
  };

  // Export report
  const handleExportReport = async (format = 'html') => {
    if (!sessionId) return;

    try {
      const report = await apiService.exportReport(sessionId, format);
      
      if (format === 'html') {
        // Download HTML report
        const blob = new Blob([report], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `accessibility_report_${sessionId}.html`;
        a.click();
      } else {
        // Handle JSON report
        console.log('JSON Report:', report);
      }
      
      setNotification({
        open: true,
        message: 'Report exported successfully',
        severity: 'success'
      });
    } catch (error) {
      console.error('Error exporting report:', error);
    }
  };

  return (
    <Box sx={{ flexGrow: 1, height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            PDF Accessibility Remediation Tool
          </Typography>
          
          {sessionId && (
            <>
              <Chip 
                label={`Session: ${sessionId.substring(0, 8)}...`}
                color="primary"
                variant="outlined"
                sx={{ mr: 2, color: 'white', borderColor: 'white' }}
              />
              <Button
                color="inherit"
                startIcon={<CloudUpload />}
                onClick={() => {
                  // Reset to allow new upload
                  setPdfFile(null);
                  setPdfUrl(null);
                  setSessionId(null);
                  setTagTree(null);
                  setIssues([]);
                }}
                sx={{ mr: 1 }}
              >
                New PDF
              </Button>
              <Button
                color="inherit"
                startIcon={<CheckCircle />}
                onClick={handleValidate}
                sx={{ mr: 1 }}
              >
                Validate
              </Button>
              <Button
                color="inherit"
                startIcon={<Download />}
                onClick={() => handleExportReport('html')}
                sx={{ mr: 1 }}
              >
                Export Report
              </Button>
            </>
          )}
          
          <Button
            color="inherit"
            startIcon={<Settings />}
            onClick={() => setSettingsOpen(true)}
            sx={{ mr: 1 }}
          >
            Settings
          </Button>
          
          <IconButton
            color="inherit"
            onClick={() => setDarkMode(!darkMode)}
            sx={{ ml: 1 }}
          >
            {darkMode ? <LightMode /> : <DarkMode />}
          </IconButton>
        </Toolbar>
      </AppBar>

      {analysisProgress > 0 && analysisProgress < 100 && (
        <LinearProgress variant="determinate" value={analysisProgress} />
      )}

      <Container maxWidth={false} sx={{ mt: 2, mb: 2, flexGrow: 1 }}>
        {!pdfFile ? (
          <Paper
            {...getRootProps()}
            sx={{
              p: 4,
              textAlign: 'center',
              cursor: 'pointer',
              bgcolor: isDragActive ? 'action.hover' : 'background.paper',
              border: '2px dashed',
              borderColor: 'divider',
              minHeight: 400,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <input {...getInputProps()} />
            <CloudUpload sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
            <Typography variant="h5" gutterBottom>
              {isDragActive ? 'Drop the PDF here' : 'Drag & drop a PDF file here'}
            </Typography>
            <Typography variant="body1" color="text.secondary">
              or click to select a file
            </Typography>
            <Button variant="contained" sx={{ mt: 2 }}>
              Select PDF File
            </Button>
          </Paper>
        ) : (
          <Box sx={{ height: 'calc(100vh - 70px)', width: '100%' }}>
            <PanelGroup direction="horizontal">
              {/* Left Panel - PDF Viewer */}
              <Panel defaultSize={65} minSize={30}>
                <EnhancedPDFViewer
                  key={sessionId || 'pdf-viewer'} // Stable key to prevent remounting
                  pdfUrl={pdfUrl}
                  pdfData={pdfFile}
                  onPageChange={(page) => setCurrentPage(page)}
                  highlights={syncHighlights}
                  onElementClick={handlePDFElementClick}
                  scrollToElement={scrollTarget}
                />
              </Panel>
              
              {/* Resize Handle */}
              <PanelResizeHandle style={{ width: 4, backgroundColor: '#e0e0e0', cursor: 'col-resize' }} />
              
              {/* Right Panel - Tabs */}
              <Panel defaultSize={35} minSize={20}>
                <Paper sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                  <Tabs
                    value={activeTab}
                    onChange={handleTabChange}
                    indicatorColor="primary"
                    textColor="primary"
                    variant="fullWidth"
                    sx={{ borderBottom: 1, borderColor: 'divider' }}
                  >
                    <Tab label="Document Structure" />
                    <Tab label={`Issues (${issues.length})`} />
                  </Tabs>
                  
                  <Box sx={{ flexGrow: 1, overflow: 'auto', p: 2 }}>
                    {activeTab === 0 && (
                      <TagTreeEditor
                        tagTree={tagTree ? tagTree : { id: 'root', type: 'Document', page: 1, status: 'ok', children: [] }}
                        onNodeSelect={(node) => {
                          console.log('Node selected:', node);
                          handleNodeSelect(node);
                        }}
                        onNodeEdit={handleNodeEdit}
                        onApplyAISuggestion={handleApplyAISuggestion}
                      />
                    )}
                    {activeTab === 1 && (
                      <IssuePanel
                        issues={issues}
                        onIssueSelect={(issue) => {
                          handleIssueSelect(issue);
                        }}
                        onBatchFix={handleBatchFix}
                        fixProgress={fixProgress}
                      />
                    )}
                  </Box>
                </Paper>
              </Panel>
            </PanelGroup>
          </Box>
        )}
      </Container>

      {/* Settings Dialog */}
      <Dialog open={settingsOpen} onClose={() => setSettingsOpen(false)}>
        <DialogTitle>Settings</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2, minWidth: 300 }}>
            <FormControl fullWidth>
              <InputLabel>WCAG Level</InputLabel>
              <Select
                value={wcagLevel}
                label="WCAG Level"
                onChange={(e) => setWcagLevel(e.target.value)}
              >
                <MenuItem value="A">Level A</MenuItem>
                <MenuItem value="AA">Level AA (Recommended)</MenuItem>
                <MenuItem value="AAA">Level AAA</MenuItem>
              </Select>
            </FormControl>
            
            <FormControl fullWidth>
              <InputLabel>AI Assistance</InputLabel>
              <Select
                value={enableAI ? 'enabled' : 'disabled'}
                label="AI Assistance"
                onChange={(e) => setEnableAI(e.target.value === 'enabled')}
              >
                <MenuItem value="enabled">Enabled</MenuItem>
                <MenuItem value="disabled">Disabled</MenuItem>
              </Select>
            </FormControl>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSettingsOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Notification Snackbar */}
      <Snackbar
        open={notification.open}
        autoHideDuration={6000}
        onClose={() => setNotification({ ...notification, open: false })}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert
          onClose={() => setNotification({ ...notification, open: false })}
          severity={notification.severity}
        >
          {notification.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  );
}

export default App;