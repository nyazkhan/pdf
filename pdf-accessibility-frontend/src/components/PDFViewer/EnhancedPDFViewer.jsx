import React, { useEffect, useRef, useState, useCallback, memo } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import { Box, Paper, IconButton, Typography, Slider, CircularProgress, Fab, Tooltip, Alert } from '@mui/material';
import {
  ZoomIn,
  ZoomOut,
  FitScreen,
  KeyboardArrowUp
} from '@mui/icons-material';
import { useInView } from 'react-intersection-observer';

// Configure PDF.js worker
if (!pdfjsLib.GlobalWorkerOptions.workerSrc) {
  const workerSrc = '/pdf.worker.min.mjs';
  const cdnWorkerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.js`;

  // Try local worker first, fallback to CDN
  fetch(workerSrc, { method: 'HEAD' })
    .then(response => {
      if (response.ok) {
        console.log('[PDF.js] Using local worker:', workerSrc);
        pdfjsLib.GlobalWorkerOptions.workerSrc = workerSrc;
      } else {
        console.log('[PDF.js] Using CDN worker:', cdnWorkerSrc);
        pdfjsLib.GlobalWorkerOptions.workerSrc = cdnWorkerSrc;
      }
    })
    .catch(() => {
      console.log('[PDF.js] Using CDN worker (fallback):', cdnWorkerSrc);
      pdfjsLib.GlobalWorkerOptions.workerSrc = cdnWorkerSrc;
    });
}

// Individual page renderer component - memoized to prevent unnecessary re-renders
const RenderedPage = memo(({
  pageNum,
  pdfDoc,
  scale,
  highlights = [],
  onElementClick,
  onRenderComplete,
  onRenderStart
}) => {
  const containerRef = useRef(null);
  const renderTaskRef = useRef(null);
  const [isRendering, setIsRendering] = useState(false);
  const [renderError, setRenderError] = useState(null);
  const lastRenderedScale = useRef(null);
  const isRenderingRef = useRef(false);

  // Render the page
  const renderPage = useCallback(async () => {
    if (!pdfDoc || !containerRef.current) {
      console.debug(`[Page ${pageNum}] Skip render: no PDF or container`);
      return;
    }

    // Skip if already rendering
    if (isRenderingRef.current) {
      console.debug(`[Page ${pageNum}] Skip render: already rendering`);
      return;
    }

    // Skip if already rendered at this scale and canvas exists in DOM
    if (lastRenderedScale.current === scale && containerRef.current?.firstChild) {
      console.debug(`[Page ${pageNum}] Skip render: already rendered at scale ${scale}`);
      return;
    }

    console.debug(`[Page ${pageNum}] Starting render at scale ${scale}`);
    isRenderingRef.current = true;
    setIsRendering(true);
    setRenderError(null);

    if (onRenderStart) {
      onRenderStart(pageNum);
    }

    try {
      // Cancel any existing render task and wait for it
      if (renderTaskRef.current) {
        console.debug(`[Page ${pageNum}] Cancelling previous render task`);
        try {
          renderTaskRef.current.cancel();
          await renderTaskRef.current.promise.catch(() => {});
        } catch (e) {
          console.debug(`[Page ${pageNum}] Error cancelling render:`, e.message);
        }
        renderTaskRef.current = null;
      }

      // Get the page
      const page = await pdfDoc.getPage(pageNum);
      console.debug(`[Page ${pageNum}] Got page object`);

      // Create viewport
      const viewport = page.getViewport({ scale });
      const devicePixelRatio = window.devicePixelRatio || 1;
      const scaledViewport = page.getViewport({ scale: scale * devicePixelRatio });

      // Always create a new canvas to avoid reuse errors
      const canvas = document.createElement('canvas');
      console.debug(`[Page ${pageNum}] Created new canvas`);
      const context = canvas.getContext('2d');

      if (!context) {
        throw new Error('Failed to get 2D context');
      }

      // Set canvas dimensions
      canvas.height = scaledViewport.height;
      canvas.width = scaledViewport.width;
      canvas.style.width = `${viewport.width}px`;
      canvas.style.height = `${viewport.height}px`;
      canvas.style.display = 'block';
      // Remove maxWidth to allow full page display
      canvas.style.width = 'auto';
      canvas.style.height = 'auto';

      console.debug(`[Page ${pageNum}] Canvas size: ${canvas.width}x${canvas.height} (display: ${viewport.width}x${viewport.height})`);

      // Clear canvas
      context.clearRect(0, 0, canvas.width, canvas.height);

      // Render PDF page
      const renderContext = {
        canvasContext: context,
        viewport: scaledViewport,
        transform: devicePixelRatio !== 1 ? [devicePixelRatio, 0, 0, devicePixelRatio, 0, 0] : null,
      };

      renderTaskRef.current = page.render(renderContext);
      await renderTaskRef.current.promise;

      console.debug(`[Page ${pageNum}] Render complete`);
      renderTaskRef.current = null;
      lastRenderedScale.current = scale;

      // Clear container and attach new canvas
      containerRef.current.innerHTML = '';
      containerRef.current.appendChild(canvas);
      console.debug(`[Page ${pageNum}] Canvas attached to DOM`);

      isRenderingRef.current = false;
      setIsRendering(false);

      if (onRenderComplete) {
        onRenderComplete(pageNum);
      }

    } catch (error) {
      renderTaskRef.current = null;
      isRenderingRef.current = false;

      if (error.name === 'RenderingCancelledException') {
        console.debug(`[Page ${pageNum}] Rendering cancelled`);
      } else {
        console.error(`[Page ${pageNum}] Render error:`, error);
        setRenderError(error.message);
      }

      setIsRendering(false);
    }
  }, [pdfDoc, pageNum, scale, onRenderComplete, onRenderStart]);

  // Render when component mounts or scale changes
  useEffect(() => {
    renderPage();
  }, [renderPage]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      console.debug(`[Page ${pageNum}] Component unmounting, cleaning up`);
      if (renderTaskRef.current) {
        try {
          renderTaskRef.current.cancel();
        } catch (e) {
          console.debug(`[Page ${pageNum}] Error cancelling on unmount:`, e.message);
        }
      }
    };
  }, [pageNum]);

  // Render highlights overlay
  const renderHighlights = () => {
    const pageHighlights = highlights.filter(h => h.page === pageNum);
    if (pageHighlights.length === 0) return null;

    return (
      <Box
        sx={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          pointerEvents: 'none',
        }}
      >
        {pageHighlights.map((highlight, index) => (
          <Box
            key={highlight.id || index}
            onClick={() => onElementClick && onElementClick(highlight.id, pageNum, highlight)}
            sx={{
              position: 'absolute',
              left: `${(highlight.x / 100) * 100}%`,
              top: `${(highlight.y / 100) * 100}%`,
              width: `${(highlight.width / 100) * 100}%`,
              height: `${(highlight.height / 100) * 100}%`,
              backgroundColor: highlight.color || 'rgba(255, 255, 0, 0.3)',
              border: `2px solid ${highlight.color || 'yellow'}`,
              pointerEvents: 'auto',
              cursor: 'pointer',
            }}
          />
        ))}
      </Box>
    );
  };

  return (
    <Box sx={{ position: 'relative', width: '100%', display: 'flex', justifyContent: 'center' }}>
      <Box
        ref={containerRef}
        sx={{
          position: 'relative',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'flex-start',
          width: '100%',
          minHeight: 0,
        }}
      />
      {isRendering && (
        <Box
          sx={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            backgroundColor: 'rgba(255, 255, 255, 0.9)',
            padding: 2,
            borderRadius: 1,
            zIndex: 1,
          }}
        >
          <CircularProgress size={30} />
          <Typography variant="caption" display="block" sx={{ mt: 1 }}>
            Loading page {pageNum}...
          </Typography>
        </Box>
      )}
      {renderError && (
        <Box
          sx={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            backgroundColor: 'rgba(255, 255, 255, 0.9)',
            padding: 2,
            borderRadius: 1,
            color: 'error.main',
          }}
        >
          <Typography variant="body2">Error loading page {pageNum}</Typography>
          <Typography variant="caption">{renderError}</Typography>
        </Box>
      )}
      {renderHighlights()}
    </Box>
  );
});

RenderedPage.displayName = 'RenderedPage';

// Page observer component
const PageObserver = ({
  pageNum,
  pdfDoc,
  scale,
  highlights,
  onElementClick,
  onPageInView,
  renderingPages,
  renderedPages,
  onRenderStart,
  onRenderComplete
}) => {
  const { ref, inView } = useInView({
    threshold: 0.1,
    rootMargin: '100px',
  });

  const [shouldRender, setShouldRender] = useState(false);

  // Determine if page should render
  useEffect(() => {
    if (inView && pdfDoc && !renderingPages.has(pageNum) && !renderedPages.has(pageNum)) {
      console.debug(`[PageObserver ${pageNum}] In view, triggering render`);
      setShouldRender(true);
    }
  }, [inView, pdfDoc, pageNum, renderingPages, renderedPages]);

  // Notify parent when page comes into view
  useEffect(() => {
    if (inView && onPageInView) {
      onPageInView(pageNum);
    }
  }, [inView, pageNum, onPageInView]);

  const minHeight = Math.max(400, 600 * scale);

  return (
    <Box
      ref={ref}
      sx={{
        minHeight: minHeight,
        mb: 2,
        position: 'relative',
        backgroundColor: 'white',
        boxShadow: 2,
        borderRadius: 1,
        overflowX: 'auto',
        overflowY: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: 2,
      }}
    >
      {shouldRender && pdfDoc ? (
        <RenderedPage
          pageNum={pageNum}
          pdfDoc={pdfDoc}
          scale={scale}
          highlights={highlights}
          onElementClick={onElementClick}
          onRenderStart={onRenderStart}
          onRenderComplete={onRenderComplete}
        />
      ) : (
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            height: '100%',
            width: '100%',
            minHeight: minHeight,
          }}
        >
          <Typography variant="body2" color="text.secondary">
            Page {pageNum}
          </Typography>
        </Box>
      )}
      <Typography
        sx={{
          position: 'absolute',
          bottom: 8,
          right: 8,
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          color: 'white',
          px: 1,
          py: 0.5,
          borderRadius: 1,
          fontSize: '0.875rem',
          zIndex: 2,
        }}
      >
        Page {pageNum}
      </Typography>
    </Box>
  );
};

// Main PDF Viewer component
const EnhancedPDFViewer = ({
  pdfUrl,
  pdfData,
  onPageChange,
  highlights = [],
  onElementClick,
  scrollToPage,
  scrollToElement
}) => {
  const containerRef = useRef(null);
  const loadingTaskRef = useRef(null);
  const pdfDocRef = useRef(null);
  const lastLoadedSource = useRef(null);

  const [pdfDoc, setPdfDoc] = useState(null);
  const [totalPages, setTotalPages] = useState(0);
  const [scale, setScale] = useState(1.0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [renderedPages, setRenderedPages] = useState(new Set());
  const [renderingPages, setRenderingPages] = useState(new Set());
  const [currentPage, setCurrentPage] = useState(1);
  const [showScrollTop, setShowScrollTop] = useState(false);

  // Cleanup function
  const cleanupPdf = useCallback(() => {
    console.log('[Cleanup] Starting PDF cleanup');

    if (loadingTaskRef.current) {
      console.log('[Cleanup] Destroying loading task');
      loadingTaskRef.current.destroy();
      loadingTaskRef.current = null;
    }

    if (pdfDocRef.current) {
      console.log('[Cleanup] Destroying PDF document');
      pdfDocRef.current.destroy();
      pdfDocRef.current = null;
    }

    setPdfDoc(null);
    setTotalPages(0);
    setRenderedPages(new Set());
    setRenderingPages(new Set());
    setError(null);
  }, []);

  // Load PDF document
  useEffect(() => {
    const loadPdf = async () => {
      // Determine source
      const currentSource = pdfData || pdfUrl;
      if (!currentSource) {
        console.log('[Load] No PDF source provided');
        return;
      }

      // Check if same source
      const sourceKey = pdfData ? `data:${pdfData.size || 'unknown'}` : `url:${pdfUrl}`;
      if (lastLoadedSource.current === sourceKey && pdfDocRef.current) {
        console.log('[Load] Same PDF already loaded:', sourceKey);
        return;
      }

      console.log('[Load] Loading new PDF:', sourceKey);

      // Cleanup previous PDF
      if (pdfDocRef.current) {
        cleanupPdf();
      }

      setLoading(true);
      setError(null);

      try {
        let loadingTask;

        if (pdfData) {
          console.log('[Load] Loading from data, type:', pdfData.constructor.name);

          let data;
          if (pdfData instanceof File || pdfData instanceof Blob) {
            console.log('[Load] Converting to ArrayBuffer, size:', pdfData.size);
            data = await pdfData.arrayBuffer();
          } else if (pdfData instanceof ArrayBuffer) {
            console.log('[Load] Using ArrayBuffer directly, size:', pdfData.byteLength);
            data = pdfData;
          } else {
            data = pdfData;
          }

          loadingTask = pdfjsLib.getDocument({
            data: data,
            cMapUrl: `https://cdn.jsdelivr.net/npm/pdfjs-dist@${pdfjsLib.version}/cmaps/`,
            cMapPacked: true,
          });
        } else if (pdfUrl) {
          console.log('[Load] Loading from URL:', pdfUrl);

          loadingTask = pdfjsLib.getDocument({
            url: pdfUrl,
            cMapUrl: `https://cdn.jsdelivr.net/npm/pdfjs-dist@${pdfjsLib.version}/cmaps/`,
            cMapPacked: true,
          });
        }

        loadingTaskRef.current = loadingTask;
        const pdf = await loadingTask.promise;

        // Verify still the current task
        if (loadingTaskRef.current !== loadingTask) {
          console.log('[Load] Task cancelled, destroying PDF');
          pdf.destroy();
          return;
        }

        console.log('[Load] PDF loaded successfully, pages:', pdf.numPages);

        if (!pdf.numPages || pdf.numPages <= 0) {
          throw new Error('Invalid PDF: No pages found');
        }

        pdfDocRef.current = pdf;
        setPdfDoc(pdf);
        setTotalPages(pdf.numPages);
        setCurrentPage(1);
        lastLoadedSource.current = sourceKey;

      } catch (error) {
        console.error('[Load] Error loading PDF:', error);

        let errorMessage = 'Failed to load PDF';
        if (error.name === 'InvalidPDFException') {
          errorMessage = 'Invalid PDF file';
        } else if (error.name === 'MissingPDFException') {
          errorMessage = 'PDF file not found';
        } else if (error.message) {
          errorMessage = error.message;
        }

        setError(errorMessage);
      } finally {
        setLoading(false);
      }
    };

    loadPdf();

    return () => {
      // Only cleanup if component is unmounting without a source
      if (!pdfData && !pdfUrl) {
        cleanupPdf();
      }
    };
  }, [pdfUrl, pdfData, cleanupPdf]);

  // Handle render start
  const handleRenderStart = useCallback((pageNum) => {
    console.debug(`[Main] Page ${pageNum} render started`);
    setRenderingPages(prev => new Set(prev).add(pageNum));
  }, []);

  // Handle render complete
  const handleRenderComplete = useCallback((pageNum) => {
    console.debug(`[Main] Page ${pageNum} render completed`);
    setRenderingPages(prev => {
      const newSet = new Set(prev);
      newSet.delete(pageNum);
      return newSet;
    });
    setRenderedPages(prev => new Set(prev).add(pageNum));
  }, []);

  // Handle page in view
  const handlePageInView = useCallback((pageNum) => {
    setCurrentPage(pageNum);
    if (onPageChange) {
      onPageChange(pageNum);
    }
  }, [onPageChange]);

  // Handle scroll
  const handleScroll = useCallback(() => {
    if (!containerRef.current) return;
    const scrollTop = containerRef.current.scrollTop;
    setShowScrollTop(scrollTop > 500);
  }, []);

  // Scroll to specific page
  useEffect(() => {
    if (scrollToPage && containerRef.current) {
      const pageElements = containerRef.current.querySelectorAll('[data-page]');
      const targetElement = pageElements[scrollToPage - 1];
      targetElement?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [scrollToPage]);

  // Scroll to specific element
  useEffect(() => {
    if (scrollToElement && containerRef.current) {
      const pageElements = containerRef.current.querySelectorAll('[data-page]');
      const targetElement = pageElements[scrollToElement.page - 1];
      if (targetElement) {
        const rect = targetElement.getBoundingClientRect();
        const elementTop = rect.top + (scrollToElement.bbox.y / rect.height) * rect.height;
        window.scrollTo({
          top: elementTop - 100,
          behavior: 'smooth'
        });
      }
    }
  }, [scrollToElement]);

  // Zoom controls
  const handleZoomIn = () => {
    setScale(prevScale => Math.min(prevScale + 0.25, 3));
  };

  const handleZoomOut = () => {
    setScale(prevScale => Math.max(prevScale - 0.25, 0.25));
  };

  const handleFitWidth = async () => {
    if (!pdfDocRef.current || !containerRef.current) return;

    try {
      const firstPage = await pdfDocRef.current.getPage(1);
      const viewport = firstPage.getViewport({ scale: 1.0 });
      // Get container width minus padding (2rem = 32px on each side)
      const containerWidth = containerRef.current.clientWidth - 64;
      const fitScale = containerWidth / viewport.width;
      // Allow scale to go lower than 0.5 for large documents
      const newScale = Math.min(Math.max(fitScale, 0.25), 3);

      console.log(`[Fit] Container: ${containerWidth}px, Page: ${viewport.width}px, Scale: ${newScale}`);
      setScale(newScale);
    } catch (error) {
      console.error('[Fit] Error calculating fit width:', error);
    }
  };

  const scrollToTop = () => {
    containerRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <Paper elevation={3} sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Toolbar */}
      <Box sx={{
        p: 1,
        borderBottom: 1,
        borderColor: 'divider',
        display: 'flex',
        alignItems: 'center',
        gap: 2,
        backgroundColor: 'background.paper',
        position: 'sticky',
        top: 0,
        zIndex: 100,
      }}>
        <Typography variant="body2">
          Page {currentPage} of {totalPages}
        </Typography>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, ml: 'auto' }}>
          <Tooltip title="Zoom Out">
            <IconButton onClick={handleZoomOut} size="small" disabled={!pdfDoc}>
              <ZoomOut />
            </IconButton>
          </Tooltip>

          <Slider
            value={scale}
            min={0.25}
            max={3}
            step={0.25}
            onChange={(_, value) => setScale(value)}
            sx={{ width: 100 }}
            disabled={!pdfDoc}
          />

          <Tooltip title="Zoom In">
            <IconButton onClick={handleZoomIn} size="small" disabled={!pdfDoc}>
              <ZoomIn />
            </IconButton>
          </Tooltip>

          <Typography variant="body2" sx={{ minWidth: 45 }}>
            {Math.round(scale * 100)}%
          </Typography>

          <Tooltip title="Fit Width">
            <IconButton onClick={handleFitWidth} size="small" disabled={!pdfDoc}>
              <FitScreen />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Error display */}
      {error && (
        <Alert severity="error" sx={{ m: 2 }}>
          {error}
        </Alert>
      )}

      {/* PDF Container */}
      <Box
        ref={containerRef}
        onScroll={handleScroll}
        sx={{
          flex: 1,
          overflowX: 'auto',
          overflowY: 'auto',
          p: 2,
          backgroundColor: 'grey.100',
        }}
      >
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
            <CircularProgress />
          </Box>
        ) : pdfDoc ? (
          <>
            {Array.from({ length: totalPages }, (_, i) => i + 1).map(pageNum => (
              <PageObserver
                key={`page-${pageNum}`}
                pageNum={pageNum}
                pdfDoc={pdfDoc}
                scale={scale}
                highlights={highlights}
                onElementClick={onElementClick}
                onPageInView={handlePageInView}
                renderingPages={renderingPages}
                renderedPages={renderedPages}
                onRenderStart={handleRenderStart}
                onRenderComplete={handleRenderComplete}
              />
            ))}
          </>
        ) : (
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
            <Typography color="text.secondary">
              No PDF loaded
            </Typography>
          </Box>
        )}
      </Box>

      {/* Scroll to top button */}
      {showScrollTop && (
        <Fab
          color="primary"
          size="small"
          onClick={scrollToTop}
          sx={{
            position: 'absolute',
            bottom: 16,
            right: 16,
          }}
        >
          <KeyboardArrowUp />
        </Fab>
      )}
    </Paper>
  );
};

export default EnhancedPDFViewer;