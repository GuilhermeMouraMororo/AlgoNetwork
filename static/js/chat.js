class ChatApp {
    constructor() {
        this.messagesContainer = document.getElementById('chat-messages');
        this.messageForm = document.getElementById('message-form');
        this.messageInput = document.getElementById('message-input');
        this.fileInput = document.getElementById('file-input');
        this.fileBtn = document.getElementById('file-btn');
        this.fileInfo = document.getElementById('file-info');
        this.usersList = document.getElementById('users-list');
        
        this.lastMessageId = 0;
        this.isNearBottom = true;
        this.initEventListeners();
        this.loadMessages();
        this.loadUsers();
        this.startPolling();
        this.setupScrollHandler();
    }
    
    setupScrollHandler() {
        this.messagesContainer.addEventListener('scroll', () => {
            const threshold = 100; // pixels from bottom
            const position = this.messagesContainer.scrollTop + this.messagesContainer.clientHeight;
            const height = this.messagesContainer.scrollHeight;
            
            this.isNearBottom = (height - position) <= threshold;
        });
    }
    
    initEventListeners() {
        this.messageForm.addEventListener('submit', (e) => this.sendMessage(e));
        this.fileBtn.addEventListener('click', () => this.fileInput.click());
        this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
    }
    
    async sendMessage(e) {
        e.preventDefault();
        
        const content = this.messageInput.value.trim();
        const file = this.fileInput.files[0];
        
        if (!content && !file) return;
        
        const formData = new FormData();
        if (content) formData.append('content', content);
        if (file) formData.append('file', file);
        
        try {
            const response = await fetch('/api/send_message', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.messageInput.value = '';
                this.fileInput.value = '';
                this.fileInfo.style.display = 'none';
                this.addMessage(result.message);
                this.scrollToBottom();
            } else {
                alert('Error sending message: ' + result.error);
            }
        } catch (error) {
            console.error('Error sending message:', error);
            alert('Error sending message');
        }
    }
    
    handleFileSelect(e) {
        const file = e.target.files[0];
        if (file) {
            this.fileInfo.innerHTML = `Selected file: ${file.name} (${this.formatFileSize(file.size)})`;
            this.fileInfo.style.display = 'block';
        }
    }
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    async loadMessages() {
        try {
            const response = await fetch('/api/messages');
            const messages = await response.json();
            
            // Only update if there are new messages
            const latestMessageId = messages.length > 0 ? Math.max(...messages.map(m => m.id)) : 0;
            if (latestMessageId > this.lastMessageId) {
                const previousScroll = this.messagesContainer.scrollTop;
                const previousHeight = this.messagesContainer.scrollHeight;
                
                this.messagesContainer.innerHTML = '';
                messages.forEach(message => this.addMessage(message));
                
                this.lastMessageId = latestMessageId;
                
                // Only scroll to bottom if user was near bottom before update
                if (this.isNearBottom) {
                    this.scrollToBottom();
                } else {
                    // Maintain scroll position relative to content
                    const newHeight = this.messagesContainer.scrollHeight;
                    this.messagesContainer.scrollTop = previousScroll + (newHeight - previousHeight);
                }
            }
        } catch (error) {
            console.error('Error loading messages:', error);
        }
    }
    
    async loadUsers() {
        try {
            const response = await fetch('/api/users');
            const users = await response.json();
            this.usersList.innerHTML = '';
            users.forEach(user => this.addUser(user));
        } catch (error) {
            console.error('Error loading users:', error);
        }
    }
    
    addMessage(message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${message.is_own ? 'own' : 'other'}`;
        
        let contentHtml = '';
        
        if (message.type === 'text') {
            contentHtml = `<div class="message-content">${this.escapeHtml(message.content)}</div>`;
        } else if (message.type === 'image') {
            contentHtml = `
                <div class="image-message">
                    <img src="/static/${message.file_path}" alt="${this.escapeHtml(message.content)}">
                </div>
            `;
        } else if (message.type === 'audio') {
            contentHtml = `
                <div class="audio-message">
                    <audio controls>
                        <source src="/static/${message.file_path}" type="audio/mpeg">
                        Your browser does not support the audio element.
                    </audio>
                </div>
            `;
        } else {
            contentHtml = `
                <div class="file-message">
                    <a href="/static/${message.file_path}" download="${this.escapeHtml(message.content)}">
                        📄 ${this.escapeHtml(message.content)}
                    </a>
                </div>
            `;
        }
        
        messageDiv.innerHTML = `
            <div class="message-header">${this.escapeHtml(message.user_email)}</div>
            ${contentHtml}
            <div class="message-time">${new Date(message.timestamp).toLocaleTimeString()}</div>
        `;
        
        this.messagesContainer.appendChild(messageDiv);
    }
    
    addUser(email) {
        const userDiv = document.createElement('div');
        userDiv.className = 'user-item';
        userDiv.textContent = email;
        this.usersList.appendChild(userDiv);
    }
    
    escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
    
    scrollToBottom() {
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }
    
    startPolling() {
        setInterval(() => {
            this.loadMessages();
            this.loadUsers();
        }, 2000);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new ChatApp();
});
