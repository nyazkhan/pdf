import { WS_BASE_URL } from '../config/api';

class WebSocketService {
  constructor() {
    this.socket = null;
    this.sessionId = null;
    this.callbacks = new Map();
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
  }

  connect(sessionId) {
    if (this.socket?.readyState === WebSocket.OPEN && this.sessionId === sessionId) {
      return;
    }

    this.disconnect();
    this.sessionId = sessionId;

    // Use native WebSocket instead of Socket.io
    const wsUrl = `${WS_BASE_URL}/ws/${sessionId}`;
    console.log('Connecting to WebSocket:', wsUrl);
    
    try {
      this.socket = new WebSocket(wsUrl);
      this.setupEventHandlers();
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
    }
  }

  setupEventHandlers() {
    if (!this.socket) return;

    this.socket.onopen = () => {
      console.log(`WebSocket connected for session ${this.sessionId}`);
      this.reconnectAttempts = 0;
      this.emit('connect', { sessionId: this.sessionId });
    };

    this.socket.onclose = () => {
      console.log('WebSocket disconnected');
      this.emit('disconnect', {});
      
      // Auto-reconnect logic
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++;
        console.log(`Attempting to reconnect... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        setTimeout(() => {
          if (this.sessionId) {
            this.connect(this.sessionId);
          }
        }, 1000 * this.reconnectAttempts);
      }
    };

    this.socket.onerror = (error) => {
      console.error('WebSocket error:', error);
      this.emit('error', error);
    };

    this.socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('WebSocket message received:', data);
        
        // Handle different message types
        if (data.type) {
          this.emit(data.type, data);
        }
        
        // Legacy message handling
        if (data.ai_processing) {
          this.emit('ai_processing', data.ai_processing);
        }
        if (data.ai_suggestions) {
          this.emit('ai_suggestions', data.ai_suggestions);
        }
        if (data.fix_applied) {
          this.emit('fix_applied', data.fix_applied);
        }
        if (data.validation_complete) {
          this.emit('validation_complete', data.validation_complete);
        }
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };
  }

  disconnect() {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
      this.sessionId = null;
      this.reconnectAttempts = 0;
    }
  }

  on(event, callback) {
    if (!this.callbacks.has(event)) {
      this.callbacks.set(event, []);
    }
    this.callbacks.get(event).push(callback);
  }

  off(event, callback) {
    const callbacks = this.callbacks.get(event);
    if (callbacks) {
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
    }
  }

  emit(event, data) {
    const callbacks = this.callbacks.get(event);
    if (callbacks) {
      callbacks.forEach(callback => callback(data));
    }
  }

  send(message) {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket is not connected. Cannot send message:', message);
    }
  }

  isConnected() {
    return this.socket?.readyState === WebSocket.OPEN;
  }
}

const websocketService = new WebSocketService();
export default websocketService;