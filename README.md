# PDF Accessibility Web Application

A powerful web-based tool for analyzing and remediating PDF accessibility issues using AI-powered suggestions and WCAG 2.1 compliance checking.

## Features

- 🔍 **Comprehensive PDF Analysis**: Detects 20+ types of accessibility issues
- 🤖 **AI-Powered Suggestions**: Automatic alt text generation and content improvements
- ✅ **WCAG 2.1 Compliance**: Full support for A, AA, and AAA compliance levels
- 🔧 **Automated Fixes**: Apply fixes without corrupting visual appearance
- 📊 **Detailed Reports**: Export accessibility reports in multiple formats
- 🚀 **Real-time Processing**: WebSocket support for live updates
- 🎯 **PDF/UA Validation**: Standards-compliant accessibility checking

## Architecture

- **Backend**: FastAPI with Python 3.8+
- **Frontend**: React with TypeScript
- **AI Models**: BLIP-2 for vision, Gemini for advanced suggestions
- **PDF Processing**: PyMuPDF for manipulation
- **Database**: SQLite for report storage

## Quick Start

### Prerequisites

- Python 3.8 or higher
- Node.js 14 or higher
- npm or yarn

### Backend Setup

```bash
# Install Python dependencies
pip install -r requirements.txt

# Set environment variables (optional)
export GEMINI_API_KEY=your_api_key_here  # For advanced AI features

# Start the FastAPI server
python start_api.py
```

The API will be available at:
- http://localhost:8000 - REST API endpoints
- http://localhost:8000/docs - Interactive API documentation
- ws://localhost:8000/ws/{session_id} - WebSocket for real-time updates

### Frontend Setup

```bash
# Navigate to frontend directory
cd pdf-accessibility-frontend

# Install dependencies
npm install

# Start development server
npm start
```

The React application will open at http://localhost:3000

## Usage

1. **Upload PDF**: Drag and drop or select a PDF file through the web interface
2. **Analysis**: The system automatically analyzes accessibility issues
3. **Review Issues**: Browse detected issues with detailed descriptions
4. **Apply Fixes**: Select and apply AI-suggested fixes
5. **Export**: Download the remediated PDF or accessibility report

## API Endpoints

### Core Endpoints

- `POST /upload` - Upload PDF for analysis
- `GET /analyze/{session_id}` - Get analysis results
- `POST /ai/suggest` - Get AI suggestions for fixes
- `POST /apply-fixes` - Apply selected fixes
- `GET /export/{session_id}` - Export remediated PDF

### Authentication

The API supports JWT-based authentication with rate limiting:

```bash
# Generate API key
curl -X POST http://localhost:8000/auth/register

# Use API key in requests
curl -H "X-API-Key: your_key_here" http://localhost:8000/analyze/...
```

## Configuration

Edit `config.yaml` to customize:

```yaml
accessibility:
  wcag_level: "AA"  # A, AA, or AAA
  auto_fix: []      # List of auto-applicable fixes

ai_models:
  vision_model: "Salesforce/blip-image-captioning-base"
  device: "cpu"     # or "cuda" for GPU

pdf_processing:
  max_pages: 500
  batch_size: 10
```

## Development

### Running Tests

```bash
# Backend tests
python -m pytest tests/

# Frontend tests
cd pdf-accessibility-frontend
npm test
```

### Testing Components

```bash
# Test PDF parser
python -m src.core.pdf_parser sample.pdf

# Test accessibility rules
python -m src.core.accessibility_rules --wcag-level AA

# Test visual integrity
python test_visual_integrity.py sample.pdf
```

## Project Structure

```
.
├── src/
│   ├── api/           # FastAPI endpoints
│   ├── core/          # PDF processing and validation
│   ├── ai/            # AI models and agents
│   └── utils/         # Utility functions
├── pdf-accessibility-frontend/  # React frontend
├── uploads/           # Temporary file storage
├── config.yaml        # Configuration
└── requirements.txt   # Python dependencies
```

## Accessibility Rules

The application implements comprehensive WCAG 2.1 rules:

### Level A (Critical)
- **1.1.1** Non-text Content (alt text)
- **1.3.1** Info and Relationships (headings, tables)
- **1.3.2** Meaningful Sequence (reading order)
- **2.4.1** Bypass Blocks (empty pages)
- **2.4.2** Page Titled (metadata)

### Level AA (Important)
- **1.4.3** Contrast (color analysis)
- **2.4.6** Headings and Labels (structure)
- **3.1.1** Language of Page (document language)

### Level AAA (Enhanced)
- Advanced color contrast ratios
- Enhanced text alternatives
- Detailed structure validation

## Performance

- Small PDFs (<10 pages): 10-30 seconds
- Medium PDFs (10-50 pages): 1-2 minutes  
- Large PDFs (50+ pages): 2-5 minutes
- AI model initialization: ~30 seconds on first run

## System Requirements

- **RAM**: 2GB minimum, 4GB recommended
- **CPU**: Multi-core recommended for AI features
- **GPU**: Optional CUDA support for faster processing
- **Storage**: 1GB for models, plus workspace

## Troubleshooting

### Common Issues

**1. Model Download Fails**
```bash
# Check internet connection and try:
python -c "from transformers import BlipProcessor; BlipProcessor.from_pretrained('Salesforce/blip-image-captioning-base')"
```

**2. GPU Not Detected**
```yaml
# In config.yaml, change to:
ai_models:
  device: "cpu"
```

**3. Large PDF Performance**
```yaml
# Reduce batch size in config:
pdf_processing:
  batch_size: 5
```

### Debug Mode
```bash
# Enable debug logging
LOG_LEVEL=DEBUG python start_api.py
```

## Contributing

Contributions are welcome! Please feel free to submit pull requests.

## License

MIT License - See LICENSE file for details.

## Support

For issues and questions, please open an issue on GitHub.

## Acknowledgments

- **Salesforce Research** for BLIP image captioning models
- **Hugging Face** for transformer model hosting
- **PyMuPDF Team** for excellent PDF processing library
- **WCAG Working Group** for accessibility guidelines
- **PDF Association** for PDF/UA standards

---

**Making PDFs accessible for everyone! 🌟**