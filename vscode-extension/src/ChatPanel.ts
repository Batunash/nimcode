import * as vscode from 'vscode';
import { spawn, ChildProcess } from 'child_process';
import * as path from 'path';

export class ChatPanel {
    public static currentPanel: ChatPanel | undefined;
    private readonly _panel: vscode.WebviewPanel;
    private readonly _extensionUri: vscode.Uri;
    private _disposables: vscode.Disposable[] = [];
    private nimcodeProcess: ChildProcess | null = null;
    
    public sessionId: string;

    private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri, sessionId: string) {
        this._panel = panel;
        this._extensionUri = extensionUri;
        this.sessionId = sessionId;

        this._panel.webview.html = this._getHtmlForWebview();
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

        this._panel.webview.onDidReceiveMessage(
            async (data) => {
                switch (data.type) {
                    case 'onInfo': {
                        if (!data.value) return;
                        vscode.window.showInformationMessage(data.value);
                        break;
                    }
                    case 'onError': {
                        if (!data.value) return;
                        vscode.window.showErrorMessage(data.value);
                        break;
                    }
                    case 'prompt': {
                        if (!this.nimcodeProcess) this.startNimcodeServer();
                        if (this.nimcodeProcess && this.nimcodeProcess.stdin) {
                            const payload = JSON.stringify({ type: 'prompt', content: data.value });
                            this.nimcodeProcess.stdin.write(payload + '\n');
                        }
                        break;
                    }
                    case 'clear': {
                        if (this.nimcodeProcess && this.nimcodeProcess.stdin) {
                            const payload = JSON.stringify({ type: 'clear' });
                            this.nimcodeProcess.stdin.write(payload + '\n');
                        }
                        break;
                    }
                    case 'action_response': {
                        if (this.nimcodeProcess && this.nimcodeProcess.stdin) {
                            const payload = JSON.stringify({ type: 'action_response', granted: data.granted });
                            this.nimcodeProcess.stdin.write(payload + '\n');
                        }
                        break;
                    }
                }
            },
            null,
            this._disposables
        );

        this.startNimcodeServer();
    }

    public static render(extensionUri: vscode.Uri, sessionId: string = "default") {
        if (ChatPanel.currentPanel) {
            if (ChatPanel.currentPanel.sessionId !== sessionId) {
                ChatPanel.currentPanel.sessionId = sessionId;
                ChatPanel.currentPanel.restartServer();
            }
            ChatPanel.currentPanel._panel.reveal(vscode.ViewColumn.One);
        } else {
            const panel = vscode.window.createWebviewPanel(
                'nimcodeChat',
                'NimCode Chat',
                vscode.ViewColumn.One,
                {
                    enableScripts: true,
                    localResourceRoots: [extensionUri],
                    retainContextWhenHidden: true
                }
            );
            ChatPanel.currentPanel = new ChatPanel(panel, extensionUri, sessionId);
        }
    }
    
    public restartServer() {
        this.startNimcodeServer();
        this._panel.webview.postMessage({ type: 'clear_ui' });
    }

    private startNimcodeServer() {
        if (this.nimcodeProcess) {
            this.nimcodeProcess.kill();
        }
        
        const workspaceRoot = vscode.workspace.workspaceFolders?.[0].uri.fsPath;
        if (!workspaceRoot) {
            vscode.window.showErrorMessage('NimCode requires an open workspace.');
            return;
        }

        try {
            // Using shell: true is critical on Windows to resolve aliases like .cmd or .exe
            this.nimcodeProcess = spawn('nimcode', ['--stdio'], { cwd: workspaceRoot, shell: true });
        } catch (e) {
            this.nimcodeProcess = spawn('python', ['-m', 'nimcode.cli', '--stdio'], { cwd: workspaceRoot, shell: true });
        }
        
        this.nimcodeProcess.on('error', (err) => {
             try {
                 this.nimcodeProcess = spawn('python', ['-m', 'nimcode.cli', '--stdio'], { cwd: workspaceRoot, shell: true });
                 this.attachProcessListeners();
             } catch (e) {
                 vscode.window.showErrorMessage('Failed to start NimCode backend. Ensure python is installed and nimcode is in your PATH.');
             }
        });
        
        this.attachProcessListeners();
    }
    
    private attachProcessListeners() {
        if (!this.nimcodeProcess) return;
        
        if (this.nimcodeProcess.stdout) {
            this.nimcodeProcess.stdout.on('data', (data) => {
                const lines = data.toString().split('\n');
                for (const line of lines) {
                    if (line.trim() === '') continue;
                    try {
                        const msg = JSON.parse(line);
                        this._panel.webview.postMessage(msg);
                    } catch (e) {
                        // Ignore non-JSON output (maybe debug prints)
                    }
                }
            });
        }
        
        if (this.nimcodeProcess.stderr) {
            this.nimcodeProcess.stderr.on('data', (data) => {
                console.error(`NimCode stderr: ${data}`);
            });
        }

        this.nimcodeProcess.on('close', (code) => {
            this.nimcodeProcess = null;
        });
    }

    public dispose() {
        ChatPanel.currentPanel = undefined;
        this._panel.dispose();
        if (this.nimcodeProcess) {
            this.nimcodeProcess.kill();
        }
        while (this._disposables.length) {
            const disposable = this._disposables.pop();
            if (disposable) {
                disposable.dispose();
            }
        }
    }

    private _getHtmlForWebview() {
        return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NimCode Chat</title>
  
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/atom-one-dark.min.css">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/highlight.min.js"></script>
  
  <style>
    body {
      font-family: var(--vscode-font-family);
      color: var(--vscode-editor-foreground);
      background-color: var(--vscode-editor-background);
      padding: 0;
      margin: 0;
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }

    .chat-container {
      flex: 1;
      overflow-y: auto;
      padding: 24px;
      padding-bottom: 140px; /* Space for the floating pill */
      display: flex;
      flex-direction: column;
      gap: 24px;
      max-width: 900px;
      margin: 0 auto;
      width: 100%;
      box-sizing: border-box;
    }
    
    .message {
      line-height: 1.6;
      font-size: 14px;
      max-width: 100%;
    }
    
    .message p { margin-top: 0; }
    .message p:last-child { margin-bottom: 0; }
    
    .message.user {
      align-self: flex-end;
      color: var(--vscode-editor-foreground);
      background-color: var(--vscode-editorWidget-background);
      padding: 12px 16px;
      border-radius: 12px;
      max-width: 80%;
      border: 1px solid var(--vscode-widget-border);
    }
    
    .message.assistant {
      align-self: flex-start;
      color: var(--vscode-editor-foreground);
      width: 100%;
    }
    
    .message.info {
      align-self: center;
      color: var(--vscode-descriptionForeground);
      text-align: center;
      font-size: 12px;
    }
    
    .message.tool-request {
      align-self: flex-start;
      background-color: var(--vscode-editorWidget-background);
      border: 1px solid var(--vscode-widget-border);
      border-radius: 8px;
      padding: 16px;
      width: 100%;
      box-sizing: border-box;
    }
    
    .tool-header {
      font-weight: 600;
      margin-bottom: 12px;
      color: var(--vscode-textLink-foreground);
      display: flex;
      align-items: center;
      gap: 8px;
    }
    
    .tool-args {
      background: var(--vscode-textCodeBlock-background);
      padding: 12px;
      border-radius: 6px;
      font-family: var(--vscode-editor-font-family);
      font-size: 13px;
      overflow-x: auto;
      margin-bottom: 16px;
    }
    
    .tool-actions {
      display: flex;
      gap: 8px;
    }

    /* Claude Code style pill input */
    .input-container {
      position: fixed;
      bottom: 24px;
      left: 50%;
      transform: translateX(-50%);
      width: calc(100% - 48px);
      max-width: 852px;
      background-color: var(--vscode-editorWidget-background);
      border: 1px solid var(--vscode-widget-border);
      border-radius: 16px;
      padding: 12px 16px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.2);
      display: flex;
      flex-direction: column;
      z-index: 100;
    }
    
    textarea {
      width: 100%;
      background-color: transparent;
      color: var(--vscode-input-foreground);
      border: none;
      font-family: inherit;
      font-size: 14px;
      resize: none;
      outline: none;
      padding: 0;
      margin-bottom: 8px;
      min-height: 22px;
      max-height: 250px;
      overflow-y: auto;
      line-height: 1.5;
    }
    
    textarea::placeholder {
      color: var(--vscode-input-placeholderForeground);
    }
    
    .controls {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    
    .controls-left {
      display: flex;
      gap: 12px;
      align-items: center;
      color: var(--vscode-descriptionForeground);
      font-size: 12px;
    }
    
    .icon-btn {
      background: none;
      border: none;
      color: var(--vscode-icon-foreground);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 4px;
      border-radius: 4px;
      opacity: 0.8;
    }
    
    .icon-btn:hover {
      background: var(--vscode-toolbar-hoverBackground);
      opacity: 1;
    }
    
    .submit-btn {
      background-color: var(--vscode-icon-foreground);
      border: none;
      width: 28px;
      height: 28px;
      border-radius: 6px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: opacity 0.2s;
    }
    
    .submit-btn:hover {
      opacity: 0.8;
    }
    
    .submit-btn svg {
      fill: var(--vscode-editorWidget-background);
    }
    
    button.secondary {
      background-color: var(--vscode-button-secondaryBackground);
      color: var(--vscode-button-secondaryForeground);
      border: none;
      padding: 6px 12px;
      border-radius: 4px;
      cursor: pointer;
      font-size: 13px;
    }
    
    button.danger {
      background-color: var(--vscode-errorForeground);
      color: white;
      border: none;
      padding: 6px 12px;
      border-radius: 4px;
      cursor: pointer;
      font-size: 13px;
    }
    
    /* Markdown Styles */
    pre {
      background-color: var(--vscode-textCodeBlock-background);
      padding: 16px;
      border-radius: 8px;
      overflow-x: auto;
      margin: 16px 0;
      border: 1px solid var(--vscode-widget-border);
    }
    code { font-family: var(--vscode-editor-font-family); }
  </style>
</head>
<body>

  <div class="chat-container" id="chat">
    <div class="message assistant">
      <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a10 10 0 1 0 10 10H12V2z"></path><path d="M12 12 2.1 7.1"></path><path d="M12 12l9.9 4.9"></path></svg>
        <strong>NimCode</strong>
      </div>
      <p>Hello! I am NimCode, your AI coding assistant.</p>
    </div>
  </div>
  
  <div class="input-container">
    <textarea id="prompt-input" rows="1" placeholder="Queue another message..."></textarea>
    <div class="controls">
      <div class="controls-left">
        <button class="icon-btn" title="Add attachment (dummy)">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"></path></svg>
        </button>
        <button class="icon-btn" title="Slash commands (dummy)">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line></svg>
        </button>
        <span style="margin-left: 8px;">Edit automatically</span>
      </div>
      <button class="submit-btn" id="send-btn" title="Send Message">
        <svg width="12" height="12" viewBox="0 0 24 24"><rect width="24" height="24" rx="4"></rect></svg>
      </button>
    </div>
  </div>

  <script>
    const vscode = acquireVsCodeApi();
    const chat = document.getElementById('chat');
    const input = document.getElementById('prompt-input');
    const sendBtn = document.getElementById('send-btn');

    // Auto-resize textarea
    input.addEventListener('input', function() {
      this.style.height = 'auto';
      this.style.height = (this.scrollHeight) + 'px';
    });

    marked.setOptions({
      highlight: function(code, lang) {
        if (lang && hljs.getLanguage(lang)) {
          return hljs.highlight(code, { language: lang }).value;
        }
        return hljs.highlightAuto(code).value;
      }
    });

    let currentAssistantMessage = null;
    let rawAssistantContent = "";

    window.addEventListener('message', event => {
      const message = event.data;
      switch (message.type) {
        case 'clear_ui':
          chat.innerHTML = '<div class="message assistant"><p>Started a new session.</p></div>';
          currentAssistantMessage = null;
          break;
        case 'info':
          const infoEl = document.createElement('div');
          infoEl.className = 'message info';
          infoEl.innerHTML = marked.parse(message.content);
          chat.appendChild(infoEl);
          chat.scrollTop = chat.scrollHeight;
          break;
        case 'chunk':
          if (!currentAssistantMessage) {
            currentAssistantMessage = document.createElement('div');
            currentAssistantMessage.className = 'message assistant markdown-body';
            
            // Add Assistant header
            const header = document.createElement('div');
            header.style = "display: flex; align-items: center; gap: 8px; margin-bottom: 12px; margin-top: 16px;";
            header.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a10 10 0 1 0 10 10H12V2z"></path><path d="M12 12 2.1 7.1"></path><path d="M12 12l9.9 4.9"></path></svg><strong>NimCode</strong>';
            
            const contentDiv = document.createElement('div');
            contentDiv.className = 'content-body';
            
            currentAssistantMessage.appendChild(header);
            currentAssistantMessage.appendChild(contentDiv);
            chat.appendChild(currentAssistantMessage);
            rawAssistantContent = "";
          }
          rawAssistantContent += message.content;
          const contentBody = currentAssistantMessage.querySelector('.content-body');
          if (contentBody) {
             contentBody.innerHTML = marked.parse(rawAssistantContent);
          }
          chat.scrollTop = chat.scrollHeight;
          break;
        case 'done':
          currentAssistantMessage = null;
          rawAssistantContent = "";
          break;
        case 'action_required':
          renderToolRequest(message.tool, message.args);
          break;
        case 'error':
          const errorEl = document.createElement('div');
          errorEl.className = 'message assistant';
          errorEl.style.color = 'var(--vscode-errorForeground)';
          errorEl.textContent = 'Error: ' + message.content;
          chat.appendChild(errorEl);
          chat.scrollTop = chat.scrollHeight;
          currentAssistantMessage = null;
          break;
      }
    });

    function renderToolRequest(tool, args) {
      const card = document.createElement('div');
      card.className = 'message tool-request';
      
      const header = document.createElement('div');
      header.className = 'tool-header';
      header.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg> Execute Tool: ' + tool;
      
      const argsDisplay = document.createElement('div');
      argsDisplay.className = 'tool-args';
      argsDisplay.textContent = JSON.stringify(args, null, 2);
      
      const actions = document.createElement('div');
      actions.className = 'tool-actions';
      
      const approveBtn = document.createElement('button');
      approveBtn.className = 'secondary';
      approveBtn.textContent = 'Approve';
      approveBtn.onclick = () => {
        card.style.opacity = '0.6';
        actions.innerHTML = '<span style="color:var(--vscode-testing-iconPassed)">✓ Approved</span>';
        vscode.postMessage({ type: 'action_response', granted: true });
      };
      
      const rejectBtn = document.createElement('button');
      rejectBtn.textContent = 'Reject';
      rejectBtn.className = 'danger';
      rejectBtn.onclick = () => {
        card.style.opacity = '0.6';
        actions.innerHTML = '<span style="color:var(--vscode-testing-iconFailed)">✗ Rejected</span>';
        vscode.postMessage({ type: 'action_response', granted: false });
      };
      
      actions.appendChild(approveBtn);
      actions.appendChild(rejectBtn);
      
      card.appendChild(header);
      card.appendChild(argsDisplay);
      card.appendChild(actions);
      
      chat.appendChild(card);
      chat.scrollTop = chat.scrollHeight;
    }

    function sendPrompt() {
      const text = input.value.trim();
      if (!text) return;
      
      const userEl = document.createElement('div');
      userEl.className = 'message user';
      userEl.textContent = text;
      chat.appendChild(userEl);
      chat.scrollTop = chat.scrollHeight;

      vscode.postMessage({ type: 'prompt', value: text });
      
      input.value = '';
      input.style.height = 'auto'; // reset height
    }

    sendBtn.addEventListener('click', sendPrompt);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendPrompt();
      }
    });
  </script>
</body>
</html>`;
    }
}
