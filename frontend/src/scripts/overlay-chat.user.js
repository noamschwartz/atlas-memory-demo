// ==UserScript==
// @name         Elastic Agent Chat Overlay
// @namespace    https://elastic.co/demos
// @version      1.2.5
// @description  Inject an AI chat assistant onto any website, powered by Elastic Agent Builder
// @author       Elastic Demo Team
// @match        *://*.gov.uk/*
// @run-at       document-end
// @grant        GM_xmlhttpRequest
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_registerMenuCommand
// @grant        GM_addStyle
// @connect      localhost
// @connect      *.run.app
// @connect      *.elastic-cloud.com
// ==/UserScript==

/**
 * Elastic Agent Chat Overlay
 * 
 * This userscript injects a floating chat widget onto any website.
 * It connects to your Elastic Demo Starter backend for secure Agent Builder access.
 * 
 * SETUP:
 * 1. Install Tampermonkey browser extension
 * 2. Create a new script and paste this code
 * 3. Configure the BACKEND_URL below to point to your deployed/local backend
 * 4. Navigate to any website and click the chat button!
 * 
 * The chat connects to your backend's /api/agent/chat endpoint which handles
 * authentication and streaming from Agent Builder.
 */

(function() {
    'use strict';

    // ═══════════════════════════════════════════════════════════════════════════
    // CONFIGURATION - Edit these values for your setup
    // ═══════════════════════════════════════════════════════════════════════════
    
    const CONFIG = {
        // Backend URL - your Elastic Demo Starter backend
        // Local: http://localhost:8001
        // Deployed: https://your-service.run.app
        backendUrl: GM_getValue('backendUrl', 'http://localhost:8001'),
        
        // Branding - these are defaults that will be overridden by backend branding
        name: GM_getValue('chatName', 'AI Assistant'),
        greeting: GM_getValue('greeting', "Hello! I'm your AI assistant. How can I help you today?"),
        primaryColor: GM_getValue('primaryColor', '#1D70B8'), // GOV.UK blue default - will be fetched from backend
        accentColor: GM_getValue('accentColor', '#00BFB3'), // Elastic teal default
        
        // Position: 'bottom-right', 'bottom-left', 'top-right', 'top-left'
        position: GM_getValue('position', 'bottom-right'),
        
        // Behaviour
        autoOpen: false,
        
        // Track if branding has been fetched
        brandingFetched: false,
    };

    // ═══════════════════════════════════════════════════════════════════════════
    // BRANDING FETCH
    // ═══════════════════════════════════════════════════════════════════════════
    
    /**
     * Fetch branding from the backend API.
     * Uses the first brand (default) from the brands list.
     */
    async function fetchBranding() {
        return new Promise((resolve) => {
            GM_xmlhttpRequest({
                method: 'GET',
                url: `${CONFIG.backendUrl}/api/branding/`,
                headers: { 'Accept': 'application/json' },
                onload: (response) => {
                    if (response.status === 200) {
                        try {
                            const brands = JSON.parse(response.responseText);
                            // Use the first brand (or 'default' if available)
                            const brand = brands.find(b => b.id === 'default') || brands[0];
                            if (brand && brand.colors) {
                                CONFIG.primaryColor = brand.colors.primary || CONFIG.primaryColor;
                                CONFIG.accentColor = brand.colors.accent || CONFIG.accentColor;
                                CONFIG.name = brand.name || CONFIG.name;
                                CONFIG.brandingFetched = true;
                                console.log('[Elastic Chat] Branding loaded:', brand.name, CONFIG.primaryColor);
                            }
                        } catch (e) {
                            console.warn('[Elastic Chat] Failed to parse branding:', e);
                        }
                    } else {
                        console.warn('[Elastic Chat] Failed to fetch branding:', response.status);
                    }
                    resolve();
                },
                onerror: () => {
                    console.warn('[Elastic Chat] Network error fetching branding, using defaults');
                    resolve();
                },
                ontimeout: () => {
                    console.warn('[Elastic Chat] Timeout fetching branding, using defaults');
                    resolve();
                },
                timeout: 5000, // 5 second timeout
            });
        });
    }

    // Register menu commands for configuration
    GM_registerMenuCommand('⚙️ Set Backend URL', () => {
        const url = prompt('Enter your backend URL:', CONFIG.backendUrl);
        if (url) {
            GM_setValue('backendUrl', url);
            CONFIG.backendUrl = url;
            alert('Backend URL updated! Refresh the page to apply.');
        }
    });
    
    GM_registerMenuCommand('🎨 Set Chat Name', () => {
        const name = prompt('Enter chat assistant name:', CONFIG.name);
        if (name) {
            GM_setValue('chatName', name);
            CONFIG.name = name;
            updateHeader();
        }
    });
    
    GM_registerMenuCommand('🎨 Set Primary Color', () => {
        const color = prompt('Enter primary color (hex):', CONFIG.primaryColor);
        if (color && /^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$/.test(color)) {
            GM_setValue('primaryColor', color);
            CONFIG.primaryColor = color;
            alert('Color updated! Refresh the page to apply.');
        }
    });
    
    GM_registerMenuCommand('🔄 Refresh Branding from Backend', async () => {
        await fetchBranding();
        if (CONFIG.brandingFetched) {
            alert(`Branding refreshed!\nName: ${CONFIG.name}\nPrimary: ${CONFIG.primaryColor}\n\nRefresh the page to apply visual changes.`);
        } else {
            alert('Failed to fetch branding from backend. Check the console for details.');
        }
    });

    // ═══════════════════════════════════════════════════════════════════════════
    // STATE
    // ═══════════════════════════════════════════════════════════════════════════
    
    const state = {
        isOpen: CONFIG.autoOpen,
        messages: [{ role: 'assistant', content: CONFIG.greeting, id: 'welcome', isComplete: true }],
        isLoading: false,
        conversationId: null,
        abortController: null,
    };

    // ═══════════════════════════════════════════════════════════════════════════
    // STYLES
    // ═══════════════════════════════════════════════════════════════════════════
    
    function injectStyles() {
        const positions = {
            'bottom-right': 'bottom: 20px; right: 20px;',
            'bottom-left': 'bottom: 20px; left: 20px;',
            'top-right': 'top: 20px; right: 20px;',
            'top-left': 'top: 20px; left: 20px;',
        };
        
        const panelPositions = {
            'bottom-right': 'bottom: 70px; right: 0;',
            'bottom-left': 'bottom: 70px; left: 0;',
            'top-right': 'top: 70px; right: 0;',
            'top-left': 'top: 70px; left: 0;',
        };
        
        // Use GM_addStyle to bypass CSP restrictions on sites like gov.uk
        GM_addStyle(`
            #elastic-chat-widget {
                position: fixed;
                ${positions[CONFIG.position]}
                z-index: 2147483647;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                font-size: 14px;
                line-height: 1.5;
            }
            
            #elastic-chat-toggle {
                width: 56px;
                height: 56px;
                border-radius: 50%;
                background: ${CONFIG.primaryColor};
                border: none;
                cursor: pointer;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                display: flex;
                align-items: center;
                justify-content: center;
                transition: transform 0.2s, box-shadow 0.2s;
            }
            
            #elastic-chat-toggle:hover {
                transform: scale(1.05);
                box-shadow: 0 6px 16px rgba(0,0,0,0.2);
            }
            
            #elastic-chat-toggle svg {
                width: 24px;
                height: 24px;
                fill: white;
                transition: transform 0.2s;
            }
            
            #elastic-chat-toggle.open svg {
                transform: rotate(45deg);
            }
            
            #elastic-chat-panel {
                display: none;
                position: absolute;
                ${panelPositions[CONFIG.position]}
                width: 380px;
                max-width: calc(100vw - 40px);
                height: 520px;
                max-height: calc(100vh - 100px);
                background: #fff;
                border-radius: 16px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.2);
                flex-direction: column;
                overflow: hidden;
            }
            
            #elastic-chat-panel.open {
                display: flex;
            }
            
            .elastic-chat-header {
                padding: 14px 16px;
                background: ${CONFIG.primaryColor};
                color: white;
                display: flex;
                align-items: center;
                justify-content: space-between;
            }
            
            .elastic-chat-header-title {
                font-weight: 600;
                font-size: 15px;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            
            .elastic-chat-header-actions {
                display: flex;
                gap: 4px;
            }
            
            .elastic-chat-header-btn {
                background: none;
                border: none;
                color: white;
                cursor: pointer;
                padding: 4px;
                opacity: 0.8;
                border-radius: 4px;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            
            .elastic-chat-header-btn:hover {
                opacity: 1;
                background: rgba(255,255,255,0.1);
            }
            
            .elastic-chat-messages {
                flex: 1;
                overflow-y: auto;
                padding: 16px;
                display: flex;
                flex-direction: column;
                gap: 12px;
            }
            
            .elastic-chat-message {
                padding: 10px 14px;
                border-radius: 16px;
                max-width: 85%;
                word-wrap: break-word;
            }
            
            .elastic-chat-message.user {
                background: ${CONFIG.primaryColor};
                color: white;
                align-self: flex-end;
                border-bottom-right-radius: 4px;
                white-space: pre-wrap;
            }
            
            .elastic-chat-message.assistant {
                background: #f0f2f5;
                color: #1a1a1a;
                align-self: flex-start;
                border-bottom-left-radius: 4px;
            }
            
            .elastic-chat-message:empty {
                display: none;
            }
            
            .elastic-chat-input-area {
                padding: 12px 16px;
                border-top: 1px solid #e4e6eb;
                display: flex;
                gap: 8px;
                background: #f5f7fa;
            }
            
            .elastic-chat-input {
                flex: 1;
                padding: 10px 14px;
                border: 1px solid #e4e6eb;
                border-radius: 20px;
                outline: none;
                font-size: 14px;
                font-family: inherit;
                resize: none;
                min-height: 40px;
                max-height: 100px;
            }
            
            .elastic-chat-input:focus {
                border-color: ${CONFIG.primaryColor};
                box-shadow: 0 0 0 2px ${CONFIG.primaryColor}20;
            }
            
            .elastic-chat-input:disabled {
                background: #f0f2f5;
            }
            
            .elastic-chat-send {
                width: 40px;
                height: 40px;
                border-radius: 50%;
                background: ${CONFIG.primaryColor};
                color: white;
                border: none;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: opacity 0.2s;
            }
            
            .elastic-chat-send:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }
            
            .elastic-chat-send:not(:disabled):hover {
                opacity: 0.9;
            }
            
            .typing-dots {
                display: flex;
                gap: 4px;
            }
            
            .typing-dots span {
                width: 6px;
                height: 6px;
                background: #999;
                border-radius: 50%;
                animation: typing 1.4s infinite;
            }
            
            .typing-dots span:nth-child(2) { animation-delay: 0.2s; }
            .typing-dots span:nth-child(3) { animation-delay: 0.4s; }
            
            @keyframes typing {
                0%, 60%, 100% { transform: translateY(0); opacity: 0.5; }
                30% { transform: translateY(-4px); opacity: 1; }
            }
            
            /* Meta sections (reasoning, tools) */
            .elastic-chat-meta {
                font-size: 11px;
                color: #666;
                margin-top: 8px;
                padding-top: 8px;
                border-top: 1px solid rgba(0,0,0,0.08);
            }
            
            .elastic-chat-meta summary {
                cursor: pointer;
                user-select: none;
                padding: 2px 0;
            }
            
            .elastic-chat-meta summary:hover {
                color: #333;
            }
            
            .ec-reasoning-list {
                margin: 6px 0 0 0;
                padding-left: 20px;
                font-style: italic;
            }
            
            .ec-reasoning-list li {
                margin: 4px 0;
                line-height: 1.4;
            }
            
            .ec-tool-list {
                margin: 6px 0 0 0;
                padding-left: 0;
                list-style: none;
            }
            
            .ec-tool-item {
                margin: 4px 0;
                display: flex;
                align-items: center;
                gap: 6px;
            }
            
            .ec-tool-item.pending {
                color: ${CONFIG.primaryColor};
            }
            
            .ec-tool-item.complete {
                color: #28a745;
            }
            
            /* Live reasoning during streaming */
            .elastic-chat-live-reasoning {
                margin-bottom: 10px;
                padding: 10px 12px;
                background: #f3f0ff;
                border-radius: 8px;
                border-left: 3px solid #9370DB;
                border: 1px solid #d4c8f5;
            }
            
            .ec-reasoning-header {
                display: flex;
                align-items: center;
                gap: 6px;
                font-size: 12px;
                font-weight: 500;
                color: #6a5acd;
                margin-bottom: 8px;
            }
            
            .ec-sparkle {
                animation: sparkle 2s ease-in-out infinite;
            }
            
            @keyframes sparkle {
                0%, 100% { opacity: 1; transform: scale(1); }
                50% { opacity: 0.7; transform: scale(1.1); }
            }
            
            .ec-reasoning-steps {
                padding-left: 8px;
                border-left: 2px solid rgba(147, 112, 219, 0.3);
            }
            
            .ec-reasoning-step {
                display: flex;
                gap: 8px;
                margin: 6px 0;
                font-size: 11px;
                color: #555;
                animation: slideIn 0.2s ease-out forwards;
                opacity: 0;
            }
            
            /* Animation delays for reasoning steps using nth-child */
            .ec-reasoning-step:nth-child(1) { animation-delay: 0s; }
            .ec-reasoning-step:nth-child(2) { animation-delay: 0.05s; }
            .ec-reasoning-step:nth-child(3) { animation-delay: 0.1s; }
            .ec-reasoning-step:nth-child(4) { animation-delay: 0.15s; }
            .ec-reasoning-step:nth-child(5) { animation-delay: 0.2s; }
            .ec-reasoning-step:nth-child(6) { animation-delay: 0.25s; }
            .ec-reasoning-step:nth-child(7) { animation-delay: 0.3s; }
            .ec-reasoning-step:nth-child(8) { animation-delay: 0.35s; }
            .ec-reasoning-step:nth-child(9) { animation-delay: 0.4s; }
            .ec-reasoning-step:nth-child(10) { animation-delay: 0.45s; }
            .ec-reasoning-step:nth-child(n+11) { animation-delay: 0.5s; }
            
            @keyframes slideIn {
                from { opacity: 0; transform: translateY(-4px); }
                to { opacity: 1; transform: translateY(0); }
            }
            
            .ec-step-num {
                min-width: 16px;
                color: #9370DB;
                font-weight: 500;
                font-size: 10px;
            }
            
            .ec-step-text {
                flex: 1;
                font-style: italic;
                line-height: 1.4;
            }
            
            .ec-reasoning-dots {
                display: flex;
                gap: 3px;
                padding: 6px 0 0 16px;
            }
            
            .ec-reasoning-dots span {
                width: 4px;
                height: 4px;
                background: #9370DB;
                border-radius: 50%;
                animation: pulse 1.4s ease-in-out infinite;
            }
            
            .ec-reasoning-dots span:nth-child(2) { animation-delay: 0.2s; }
            .ec-reasoning-dots span:nth-child(3) { animation-delay: 0.4s; }
            
            @keyframes pulse {
                0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
                40% { opacity: 1; transform: scale(1); }
            }
            
            /* Loading indicator */
            .elastic-chat-loading {
                display: flex;
                align-items: center;
                gap: 8px;
                color: #666;
                font-size: 13px;
            }
            
            /* Markdown styles */
            .ec-content {
                line-height: 1.6;
            }
            
            .ec-content p, .ec-paragraph {
                margin: 0 0 0.6em 0;
            }
            
            .ec-content p:last-child, .ec-paragraph:last-child {
                margin-bottom: 0;
            }
            
            .ec-h3 {
                font-size: 1.1em;
                font-weight: 600;
                margin: 0.8em 0 0.4em 0;
            }
            
            .ec-h4 {
                font-size: 1em;
                font-weight: 600;
                margin: 0.6em 0 0.3em 0;
            }
            
            .ec-list {
                margin: 0.4em 0;
                padding-left: 1.4em;
            }
            
            .ec-list li {
                margin: 0.2em 0;
                line-height: 1.5;
            }
            
            .ec-inline-code {
                background: rgba(0,0,0,0.06);
                padding: 0.15em 0.4em;
                border-radius: 3px;
                font-family: 'SF Mono', Monaco, 'Courier New', monospace;
                font-size: 0.88em;
            }
            
            .ec-code-block {
                background: rgba(0,0,0,0.06);
                padding: 10px 12px;
                border-radius: 6px;
                margin: 0.6em 0;
                overflow-x: auto;
                font-family: 'SF Mono', Monaco, 'Courier New', monospace;
                font-size: 0.85em;
                line-height: 1.5;
            }
            
            .ec-code-block code {
                background: none;
                padding: 0;
            }
            
            .ec-blockquote {
                border-left: 3px solid ${CONFIG.primaryColor};
                margin: 0.6em 0;
                padding-left: 1em;
                color: #555;
                font-style: italic;
            }
            
            .ec-hr {
                border: none;
                border-top: 1px solid rgba(0,0,0,0.1);
                margin: 0.8em 0;
            }
            
            .ec-content a {
                color: ${CONFIG.primaryColor};
                text-decoration: underline;
            }
            
            .ec-content a:hover {
                text-decoration: none;
            }
            
            .ec-content strong {
                font-weight: 600;
            }
        `);
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // UI
    // ═══════════════════════════════════════════════════════════════════════════
    
    function createWidget() {
        const widget = document.createElement('div');
        widget.id = 'elastic-chat-widget';
        widget.innerHTML = `
            <div id="elastic-chat-panel">
                <div class="elastic-chat-header">
                    <div class="elastic-chat-header-title">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
                        </svg>
                        <span id="elastic-chat-name">${escapeHtml(CONFIG.name)}</span>
                    </div>
                    <div class="elastic-chat-header-actions">
                        <button class="elastic-chat-header-btn" id="elastic-chat-reset" title="New conversation">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                                <path d="M17.65 6.35A7.958 7.958 0 0012 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0112 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
                            </svg>
                        </button>
                        <button class="elastic-chat-header-btn" id="elastic-chat-close" title="Close">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                                <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                            </svg>
                        </button>
                    </div>
                </div>
                <div class="elastic-chat-messages" id="elastic-chat-messages"></div>
                <div class="elastic-chat-input-area">
                    <textarea 
                        class="elastic-chat-input" 
                        id="elastic-chat-input" 
                        placeholder="Type a message..."
                        rows="1"
                    ></textarea>
                    <button class="elastic-chat-send" id="elastic-chat-send" title="Send">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
                        </svg>
                    </button>
                </div>
            </div>
            <button id="elastic-chat-toggle" title="Chat with AI">
                <svg viewBox="0 0 24 24">
                    <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
                </svg>
            </button>
        `;
        document.body.appendChild(widget);
        
        // Event listeners
        document.getElementById('elastic-chat-toggle').addEventListener('click', toggleChat);
        document.getElementById('elastic-chat-close').addEventListener('click', () => toggleChat(false));
        document.getElementById('elastic-chat-reset').addEventListener('click', resetConversation);
        document.getElementById('elastic-chat-send').addEventListener('click', handleSend);
        
        const input = document.getElementById('elastic-chat-input');
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
            }
        });
        
        // Note: Auto-resize removed due to CSP restrictions on gov.uk
        // The textarea uses CSS min/max-height instead
        
        renderMessages();
        
        if (state.isOpen) {
            document.getElementById('elastic-chat-panel').classList.add('open');
            document.getElementById('elastic-chat-toggle').classList.add('open');
        }
    }
    
    function toggleChat(forceState) {
        state.isOpen = typeof forceState === 'boolean' ? forceState : !state.isOpen;
        document.getElementById('elastic-chat-panel').classList.toggle('open', state.isOpen);
        document.getElementById('elastic-chat-toggle').classList.toggle('open', state.isOpen);
        
        if (state.isOpen) {
            document.getElementById('elastic-chat-input').focus();
        }
    }
    
    function updateHeader() {
        const nameEl = document.getElementById('elastic-chat-name');
        if (nameEl) nameEl.textContent = CONFIG.name;
    }
    
    /**
     * Simple markdown parser for userscript (no external dependencies).
     * Handles: bold, italic, code, links, lists, headers, blockquotes.
     */
    function parseMarkdown(text) {
        if (!text) return '';
        
        // First escape HTML (but we'll allow our own tags)
        let html = text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
        
        // Code blocks (```code```) - do first to avoid processing inside
        html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
            return `<pre class="ec-code-block"><code>${code.trim()}</code></pre>`;
        });
        
        // Inline code (`code`)
        html = html.replace(/`([^`]+)`/g, '<code class="ec-inline-code">$1</code>');
        
        // Headers (### Header)
        html = html.replace(/^### (.+)$/gm, '<h4 class="ec-h4">$1</h4>');
        html = html.replace(/^## (.+)$/gm, '<h3 class="ec-h3">$1</h3>');
        html = html.replace(/^# (.+)$/gm, '<h3 class="ec-h3">$1</h3>');
        
        // Bold and italic
        html = html.replace(/\*\*\*([^*]+)\*\*\*/g, '<strong><em>$1</em></strong>');
        html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
        html = html.replace(/___([^_]+)___/g, '<strong><em>$1</em></strong>');
        html = html.replace(/__([^_]+)__/g, '<strong>$1</strong>');
        html = html.replace(/_([^_]+)_/g, '<em>$1</em>');
        
        // Links [text](url)
        html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
        
        // Unordered lists (- item or * item)
        html = html.replace(/^[\-\*] (.+)$/gm, '<li>$1</li>');
        html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul class="ec-list">$&</ul>');
        
        // Numbered lists (1. item)
        html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');
        // Wrap consecutive list items in ol (if not already in ul)
        html = html.replace(/(?<!<\/ul>)(<li>.*<\/li>\n?)+(?!<\/ul>)/g, (match) => {
            if (!match.includes('<ul')) {
                return '<ol class="ec-list">' + match + '</ol>';
            }
            return match;
        });
        
        // Blockquotes (> text)
        html = html.replace(/^&gt; (.+)$/gm, '<blockquote class="ec-blockquote">$1</blockquote>');
        
        // Horizontal rules
        html = html.replace(/^---+$/gm, '<hr class="ec-hr">');
        
        // Convert newlines to <br> for non-block elements
        // But preserve paragraph structure
        html = html.replace(/\n\n/g, '</p><p class="ec-paragraph">');
        html = html.replace(/\n/g, '<br>');
        
        // Wrap in paragraph if not already in a block element
        if (!html.startsWith('<')) {
            html = '<p class="ec-paragraph">' + html + '</p>';
        }
        
        // Clean up empty paragraphs
        html = html.replace(/<p class="ec-paragraph"><\/p>/g, '');
        html = html.replace(/<p class="ec-paragraph">(<(?:ul|ol|pre|h[1-6]|blockquote))/g, '$1');
        html = html.replace(/(<\/(?:ul|ol|pre|h[1-6]|blockquote)>)<\/p>/g, '$1');
        
        return html;
    }
    
    function renderMessages() {
        const container = document.getElementById('elastic-chat-messages');
        container.innerHTML = state.messages.map(msg => {
            const isStreaming = state.isLoading && msg.role === 'assistant' && !msg.isComplete;
            const hasContent = msg.content && msg.content.trim();
            const hasReasoning = msg.reasoning && msg.reasoning.length > 0;
            const hasTools = msg.toolCalls && msg.toolCalls.length > 0;
            
            // Debug: Log render state for assistant messages
            if (msg.role === 'assistant' && state.isLoading) {
                console.log('[Elastic Chat] Render state:', {
                    isStreaming,
                    hasContent,
                    hasReasoning,
                    hasTools,
                    isComplete: msg.isComplete,
                    reasoningCount: msg.reasoning?.length || 0
                });
            }
            
            // For assistant messages, use markdown parser
            const contentHtml = msg.role === 'assistant' 
                ? parseMarkdown(msg.content)
                : escapeHtml(msg.content);
            
            let html = `<div class="elastic-chat-message ${msg.role}">`;
            
            // Show live reasoning during streaming BEFORE content
            if (msg.role === 'assistant' && hasReasoning && !msg.isComplete) {
                console.log('[Elastic Chat] Rendering live reasoning with', msg.reasoning.length, 'steps');
                html += renderLiveReasoning(msg.reasoning);
            }
            
            // Message content
            if (hasContent) {
                html += `<div class="ec-content">${contentHtml}</div>`;
            } else if (isStreaming && !hasReasoning) {
                // Only show typing dots if no reasoning to display
                html += `
                    <div class="elastic-chat-loading">
                        <div class="typing-dots">
                            <span></span><span></span><span></span>
                        </div>
                        <span>Thinking...</span>
                    </div>
                `;
            }
            
            // Show completed reasoning (collapsible) after message is done
            if (hasReasoning && msg.isComplete) {
                html += `
                    <div class="elastic-chat-meta">
                        <details>
                            <summary>✨ ${msg.reasoning.length} reasoning step${msg.reasoning.length > 1 ? 's' : ''}</summary>
                            <ol class="ec-reasoning-list">
                                ${msg.reasoning.map(r => `<li>${escapeHtml(r)}</li>`).join('')}
                            </ol>
                        </details>
                    </div>
                `;
            }
            
            // Show tool calls
            if (hasTools) {
                const pendingTools = msg.toolCalls.filter(t => t.status === 'pending').length;
                const statusText = pendingTools > 0 
                    ? `${pendingTools} running...` 
                    : `${msg.toolCalls.length} completed`;
                
                html += `
                    <div class="elastic-chat-meta">
                        <details ${!msg.isComplete ? 'open' : ''}>
                            <summary>🔧 ${msg.toolCalls.length} tool call${msg.toolCalls.length > 1 ? 's' : ''} (${statusText})</summary>
                            <ul class="ec-tool-list">
                                ${msg.toolCalls.map(t => `
                                    <li class="ec-tool-item ${t.status}">
                                        <span class="ec-tool-status">${t.status === 'pending' ? '⏳' : '✓'}</span>
                                        ${escapeHtml(t.name || t.id)}
                                    </li>
                                `).join('')}
                            </ul>
                        </details>
                    </div>
                `;
            }
            
            html += '</div>';
            return html;
        }).join('');
        
        // Smart scrolling:
        // - While streaming: scroll to bottom to see latest content
        // - After complete: scroll to show start of the response
        const assistantMessages = container.querySelectorAll('.elastic-chat-message.assistant');
        const lastAssistant = assistantMessages.length > 0 ? assistantMessages[assistantMessages.length - 1] : null;
        const lastMsg = state.messages[state.messages.length - 1];
        
        if (lastAssistant && lastMsg && lastMsg.role === 'assistant') {
            if (lastMsg.isComplete) {
                // Response complete - scroll to show the START of the message
                lastAssistant.scrollIntoView({ block: 'start' });
            } else {
                // Still streaming - keep bottom in view to see new content
                container.scrollTop = container.scrollHeight;
            }
        } else {
            // User message or no messages - scroll to bottom
            container.scrollTop = container.scrollHeight;
        }
    }
    
    /**
     * Render live reasoning steps during streaming (expanded, animated).
     * Note: No inline styles - all styles via CSS classes for CSP compliance.
     */
    function renderLiveReasoning(steps) {
        if (!steps || steps.length === 0) return '';
        
        const html = `
            <div class="elastic-chat-live-reasoning">
                <div class="ec-reasoning-header">
                    <span class="ec-sparkle">*</span>
                    <span>Thinking... (${steps.length} steps)</span>
                </div>
                <div class="ec-reasoning-steps">
                    ${steps.map((step, i) => `
                        <div class="ec-reasoning-step">
                            <span class="ec-step-num">${i + 1}.</span>
                            <span class="ec-step-text">${escapeHtml(step)}</span>
                        </div>
                    `).join('')}
                    <div class="ec-reasoning-dots">
                        <span></span><span></span><span></span>
                    </div>
                </div>
            </div>
        `;
        console.log('[Elastic Chat] Live reasoning HTML:', html.substring(0, 200) + '...');
        return html;
    }
    
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    function resetConversation() {
        state.messages = [{ role: 'assistant', content: CONFIG.greeting, id: 'welcome', isComplete: true }];
        state.conversationId = null;
        state.isLoading = false;
        if (state.abortController) {
            state.abortController.abort();
            state.abortController = null;
        }
        renderMessages();
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // CHAT API
    // ═══════════════════════════════════════════════════════════════════════════
    
    async function handleSend() {
        const input = document.getElementById('elastic-chat-input');
        const query = input.value.trim();
        
        if (!query || state.isLoading) return;
        
        // Add user message
        state.messages.push({ role: 'user', content: query, id: `user-${Date.now()}`, isComplete: true });
        input.value = '';
        // Note: Cannot reset height via JS due to CSP - textarea has fixed CSS height
        state.isLoading = true;
        
        // Create assistant placeholder
        const assistantId = `assistant-${Date.now()}`;
        state.messages.push({ 
            role: 'assistant', 
            content: '', 
            id: assistantId,
            reasoning: [],
            toolCalls: [],
            isComplete: false,
        });
        
        renderMessages();
        updateSendButton();
        
        try {
            await streamChat(query, assistantId);
        } catch (error) {
            console.error('[Elastic Chat] Error:', error);
            const msg = state.messages.find(m => m.id === assistantId);
            if (msg) {
                msg.content = msg.content || `Sorry, I encountered an error: ${error.message}`;
                msg.isComplete = true;
            }
        }
        
        // Ensure message is marked complete
        const msg = state.messages.find(m => m.id === assistantId);
        if (msg) {
            msg.isComplete = true;
        }
        
        state.isLoading = false;
        renderMessages();
        updateSendButton();
    }
    
    function updateSendButton() {
        const input = document.getElementById('elastic-chat-input');
        const send = document.getElementById('elastic-chat-send');
        send.disabled = state.isLoading || !input.value.trim();
        input.disabled = state.isLoading;
        input.placeholder = state.isLoading ? 'Waiting for response...' : 'Type a message...';
    }
    
    async function streamChat(query, assistantId) {
        const url = `${CONFIG.backendUrl}/api/agent/chat`;
        
        return new Promise((resolve, reject) => {
            // Use responseType: 'stream' for real-time streaming (Tampermonkey 4.14+)
            // This provides a ReadableStream that we can process chunk-by-chunk
            GM_xmlhttpRequest({
                method: 'POST',
                url: url,
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'text/event-stream',
                },
                data: JSON.stringify({
                    input: query,
                    conversation_id: state.conversationId,
                }),
                responseType: 'stream',
                onloadstart: (response) => {
                    // Check for error status first
                    if (response.status >= 400) {
                        const msg = state.messages.find(m => m.id === assistantId);
                        if (msg) {
                            msg.content = `Error ${response.status}: Request failed`;
                        }
                        renderMessages();
                        reject(new Error(`HTTP ${response.status}`));
                        return;
                    }
                    
                    // response.response is a ReadableStream when responseType is 'stream'
                    const reader = response.response.getReader();
                    const decoder = new TextDecoder();
                    let buffer = '';
                    
                    console.log('[Elastic Chat] Stream started, processing chunks in real-time');
                    
                    function processChunk() {
                        reader.read().then(({ done, value }) => {
                            if (done) {
                                // Process any remaining buffer
                                if (buffer.trim()) {
                                    parseSSEChunk(buffer, assistantId);
                                }
                                console.log('[Elastic Chat] Stream complete');
                                resolve();
                                return;
                            }
                            
                            // Decode the chunk and add to buffer
                            const text = decoder.decode(value, { stream: true });
                            buffer += text;
                            
                            // Process complete SSE events (end with double newline)
                            // But also process partial events to show progress
                            const events = buffer.split('\n\n');
                            // Keep the last potentially incomplete event in the buffer
                            buffer = events.pop() || '';
                            
                            // Process complete events
                            for (const event of events) {
                                if (event.trim()) {
                                    parseSSEChunk(event + '\n\n', assistantId);
                                }
                            }
                            
                            // Continue reading
                            processChunk();
                        }).catch(err => {
                            console.error('[Elastic Chat] Stream read error:', err);
                            reject(err);
                        });
                    }
                    
                    // Start processing chunks
                    processChunk();
                },
                onerror: (error) => {
                    console.error('[Elastic Chat] Network error:', error);
                    reject(new Error('Network error - is the backend running at ' + CONFIG.backendUrl + '?'));
                },
                ontimeout: () => {
                    console.error('[Elastic Chat] Request timed out');
                    reject(new Error('Request timed out'));
                },
            });
        });
    }
    
    /**
     * Parse SSE chunks and extract events.
     * SSE format:
     *   event: event_name
     *   data: {"data": {...}}
     *   
     *   : comment (keep-alive)
     */
    function parseSSEChunk(chunk, assistantId) {
        const lines = chunk.split('\n');
        let currentEvent = null;
        
        for (const line of lines) {
            // Skip empty lines and comments (keep-alive pings)
            if (!line || line.startsWith(':')) continue;
            
            if (line.startsWith('event: ')) {
                currentEvent = line.slice(7).trim();
            } else if (line.startsWith('data: ')) {
                try {
                    const jsonStr = line.slice(6);
                    const parsed = JSON.parse(jsonStr);
                    
                    // Extract the actual data (it's wrapped in {"data": ...})
                    const eventData = parsed.data || parsed;
                    
                    // Use the event type from the 'event:' line, or from the data itself
                    const eventType = currentEvent || eventData.event || eventData.type;
                    
                    handleSSEEvent({ event: eventType, data: eventData }, assistantId);
                    
                    // Reset for next event
                    currentEvent = null;
                } catch (e) {
                    // Skip invalid JSON (might be partial)
                }
            }
        }
    }
    
    /**
     * Normalize event type - Agent Builder can send events with different names
     * or the event type might need to be inferred from the payload.
     */
    function normalizeEventType(explicitType, data) {
        // Map alternative event names to our internal names
        const typeMap = {
            'message_chunk': 'text_chunk',
            'conversation_updated': 'conversation_created',
            'conversation_id_set': 'conversation_created',
            'agent_reasoning': 'reasoning',
        };
        
        // Check explicit type first
        if (explicitType && typeMap[explicitType]) {
            return typeMap[explicitType];
        }
        if (explicitType) {
            return explicitType;
        }
        
        // Infer type from payload structure (like frontend agentApi.ts does)
        if (data.reasoning) return 'reasoning';
        if (data.tool_call_id && !data.result) return 'tool_call';
        if (data.result || data.output) return 'tool_result';
        if (data.conversation_id && data.title) return 'conversation_created';
        if (data.text_chunk || data.text) return 'text_chunk';
        if (data.message_content) return 'message_complete';
        
        return explicitType || 'unknown';
    }
    
    function handleSSEEvent(event, assistantId) {
        const msg = state.messages.find(m => m.id === assistantId);
        if (!msg) return;
        
        // Unwrap nested data (Agent Builder quirk - sometimes sends {data: {data: ...}})
        let data = event.data || event;
        if (data.data && typeof data.data === 'object') {
            data = data.data;
        }
        
        const eventType = normalizeEventType(event.event || event.type, data);
        
        // Debug logging for SSE events
        console.log('[Elastic Chat] SSE Event:', eventType, data);
        
        switch (eventType) {
            case 'conversation_created':
                if (data.conversation_id) state.conversationId = data.conversation_id;
                break;
                
            case 'reasoning':
                if (!msg.reasoning) msg.reasoning = [];
                const reasoningText = data.reasoning || '';
                if (reasoningText && !msg.reasoning.includes(reasoningText)) {
                    msg.reasoning.push(reasoningText);
                    console.log('[Elastic Chat] Reasoning step added:', reasoningText);
                }
                break;
            
            case 'thinking_complete':
                // Done thinking, about to start text output
                console.log('[Elastic Chat] Thinking complete, reasoning steps:', msg.reasoning?.length || 0);
                break;
                
            case 'tool_call':
                if (!msg.toolCalls) msg.toolCalls = [];
                msg.toolCalls.push({
                    id: data.tool_id || data.tool_call_id || 'unknown',
                    name: data.name || data.tool_name || '',
                    status: 'pending',
                });
                break;
                
            case 'tool_result':
                if (msg.toolCalls && msg.toolCalls.length > 0) {
                    msg.toolCalls[msg.toolCalls.length - 1].status = 'complete';
                }
                break;
                
            case 'text_chunk':
                // Main text content
                const textChunk = data.text_chunk || data.text || '';
                if (textChunk) msg.content += textChunk;
                break;
                
            case 'message_complete':
                // Final message - only use if we don't have streamed content
                if (!msg.content && data.message_content) {
                    msg.content = data.message_content;
                }
                msg.isComplete = true;
                break;
            
            case 'round_complete':
                // Round finished - mark as complete
                msg.isComplete = true;
                break;
                
            case 'error':
                msg.content = msg.content || `Error: ${data.message || data.error || 'Unknown error'}`;
                break;
                
            default:
                // Unknown event - log but don't fail
                console.log('[Elastic Chat] Unknown event type:', eventType);
                break;
        }
        
        renderMessages();
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // INITIALIZATION
    // ═══════════════════════════════════════════════════════════════════════════
    
    async function init() {
        // Don't inject on the demo starter itself
        if (window.location.hostname === 'localhost' && 
            (window.location.port === '3000' || window.location.port === '3001')) {
            return;
        }
        
        try {
            // Fetch branding from backend FIRST, then inject styles
            // This ensures we use the correct brand colors
            await fetchBranding();
            
            injectStyles();
            createWidget();
            console.log('[Elastic Chat] Ready. Backend:', CONFIG.backendUrl, 'Primary:', CONFIG.primaryColor);
        } catch (error) {
            console.error('[Elastic Chat] Failed to initialize:', error);
        }
    }
    
    // Wait for DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
