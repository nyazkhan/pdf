export const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
export const WS_BASE_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8000';

// Demo API key for development
export const DEMO_API_KEY = 'demo_key_123';

export const API_ENDPOINTS = {
  upload: '/api/upload',
  analyze: '/api/analyze',
  aiSuggest: '/api/ai/suggest',
  aiAltText: '/api/ai/alt_text',
  fix: '/api/fix',
  validate: '/api/validate',
  exportReport: '/api/export/report',
  sessionStatus: '/api/session/:sessionId/status',
  health: '/health',
  register: '/api/auth/register',
  token: '/api/auth/token',
  usage: '/api/usage',
};