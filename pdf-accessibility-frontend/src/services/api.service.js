import axios from 'axios';
import { API_BASE_URL, DEMO_API_KEY } from '../config/api';

class ApiService {
  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'X-API-Key': DEMO_API_KEY,
        'Content-Type': 'application/json',
      },
    });

    // Add response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 429) {
          console.error('Rate limit exceeded');
        }
        return Promise.reject(error);
      }
    );
  }

  async uploadPDF(file) {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await this.client.post('/api/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        const percentCompleted = progressEvent.total
          ? Math.round((progressEvent.loaded * 100) / progressEvent.total)
          : 0;
        console.log(`Upload progress: ${percentCompleted}%`);
      },
    });
    
    return response.data;
  }

  async analyzePDF(filePath, wcagLevel = 'AA', includeAISuggestions = true) {
    const response = await this.client.post('/api/analyze', {
      file_path: filePath,
      wcag_level: wcagLevel,
      include_ai_suggestions: includeAISuggestions,
    });
    return response.data;
  }

  async getAISuggestions(sessionId, elements) {
    const response = await this.client.post('/api/ai/suggest', {
      session_id: sessionId,
      elements,
    });
    return response.data;
  }

  async generateAltText(sessionId, imageData, context, pageNumber) {
    const response = await this.client.post('/api/ai/alt_text', {
      session_id: sessionId,
      image_data: imageData,
      context,
      page_number: pageNumber,
    });
    return response.data;
  }

  async applyFixes(sessionId, fixes, applyInvisible = true) {
    const response = await this.client.post('/api/fix', {
      session_id: sessionId,
      fixes,
      apply_invisible: applyInvisible,
    });
    return response.data;
  }

  async validatePDF(sessionId, profile = 'PDFUA_1') {
    const response = await this.client.post('/api/validate', {
      session_id: sessionId,
      profile,
    });
    return response.data;
  }

  async exportReport(sessionId, format = 'html') {
    const response = await this.client.post(
      `/api/export/report?session_id=${sessionId}&format=${format}`,
      {},
      {
        responseType: format === 'html' ? 'blob' : 'json',
      }
    );
    return response.data;
  }

  async getSessionStatus(sessionId) {
    const response = await this.client.get(`/api/session/${sessionId}/status`);
    return response.data;
  }

  async deleteSession(sessionId) {
    const response = await this.client.delete(`/api/session/${sessionId}`);
    return response.data;
  }

  async getPDFUrl(sessionId) {
    // Return the URL to download the PDF from the backend with API key parameter
    return `${API_BASE_URL}/api/download/${sessionId}?api_key=${DEMO_API_KEY}`;
  }
}

const apiService = new ApiService();
export default apiService;