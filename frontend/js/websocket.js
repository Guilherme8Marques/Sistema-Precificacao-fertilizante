/**
 * WebSocket Manager — Conexão com /ws/logs para logs em tempo real.
 */
class WSManager {
    constructor() {
        this.ws = null;
        this.onMessage = null;
        this.onOpen = null;
        this.onClose = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
    }

    connect() {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${protocol}//${location.host}/ws/logs`;

        this.ws = new WebSocket(url);

        this.ws.onopen = () => {
            this.reconnectAttempts = 0;
            if (this.onOpen) this.onOpen();
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (this.onMessage) this.onMessage(data);
            } catch (e) {
                console.error('WS parse error:', e);
            }
        };

        this.ws.onclose = () => {
            if (this.onClose) this.onClose();
            this._reconnect();
        };

        this.ws.onerror = () => {
            this.ws.close();
        };
    }

    _reconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) return;
        this.reconnectAttempts++;
        const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 10000);
        setTimeout(() => this.connect(), delay);
    }

    disconnect() {
        this.maxReconnectAttempts = 0;
        if (this.ws) this.ws.close();
    }
}

// Instância global
const wsManager = new WSManager();
