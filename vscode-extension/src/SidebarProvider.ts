import * as vscode from 'vscode';
import { spawn, ChildProcess } from 'child_process';

export class SidebarProvider implements vscode.WebviewViewProvider {
  _view?: vscode.WebviewView;
  private nimcodeProcess: ChildProcess | null = null;

  constructor(private readonly _extensionUri: vscode.Uri) {}

  public resolveWebviewView(webviewView: vscode.WebviewView) {
    this._view = webviewView;

    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri],
    };

    webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

    webviewView.webview.onDidReceiveMessage(async (data) => {
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
        case 'set_mode': {
           if (this.nimcodeProcess && this.nimcodeProcess.stdin) {
            const payload = JSON.stringify({ type: 'set_mode', mode: data.mode });
            this.nimcodeProcess.stdin.write(payload + '\n');
          }
          break;
        }
      }
    });

    this.startNimcodeServer();
  }

  public revive(panel: vscode.WebviewView) {
    this._view = panel;
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
        this.nimcodeProcess = spawn('nimcode', ['--stdio'], { cwd: workspaceRoot });
    } catch (e) {
        this.nimcodeProcess = spawn('python', ['-m', 'nimcode.cli', '--stdio'], { cwd: workspaceRoot });
    }
    
    if (this.nimcodeProcess.stdout) {
      this.nimcodeProcess.stdout.on('data', (data) => {
        const lines = data.toString().split('\n');
        for (const line of lines) {
          if (line.trim() === '') continue;
          try {
            const msg = JSON.parse(line);
            this._view?.webview.postMessage(msg);
          } catch (e) {
            // Ignore non-JSON output (maybe debug prints)
          }
        }
      });
    }

    this.nimcodeProcess.on('close', (code) => {
      this.nimcodeProcess = null;
    });
  }

  private _getHtmlForWebview(webview: vscode.Webview) {
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NimCode Chat</title>
  
  <!-- Markdown & Highlighting -->
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/atom-one-dark.min.css">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/highlight.min.js"></script>
  
  <style>
    body {
      font-family: var(--vscode-font-family);
      color: var(--vscode-editor-foreground);
      background-color: var(--vscode-sideBar-background);
      padding: 0;
      margin: 0;
      display: flex;
      flex-direction: column;
      height: 100vh;
    }

    .header {
      padding: 10px 16px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: var(--vscode-sideBarTitle-background);
      border-bottom: 1px solid var(--vscode-widget-border);
    }
    
    .header select {
      background: var(--vscode-dropdown-background);
      color: var(--vscode-dropdown-foreground);
      border: 1px solid var(--vscode-dropdown-border);
      padding: 4px;
      border-radius: 4px;
      outline: none;
    }

    .chat-container {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    
    .message {
      padding: 14px;
      border-radius: 8px;
      line-height: 1.6;
      font-size: 13px;
      max-width: 95%;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    
    .message p { margin-top: 0; }
    .message p:last-child { margin-bottom: 0; }
    
    .message.user {
      align-self: flex-end;
      background-color: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      border-bottom-right-radius: 2px;
    }
    
    .message.assistant {
      align-self: flex-start;
      background-color: var(--vscode-editor-background);
      border: 1px solid var(--vscode-widget-border);
      border-bottom-left-radius: 2px;
      width: 100%;
    }
    
    .message.tool-request {
      align-self: center;
      background-color: var(--vscode-editorWidget-background);
      border: 1px solid var(--vscode-focusBorder);
      width: 90%;
    }
    
    .tool-header {
      font-weight: bold;
      margin-bottom: 8px;
      color: var(--vscode-textLink-foreground);
    }
    
    .tool-args {
      background: var(--vscode-textCodeBlock-background);
      padding: 8px;
      border-radius: 4px;
      font-family: monospace;
      font-size: 12px;
      overflow-x: auto;
      margin-bottom: 12px;
    }
    
    .tool-actions {
      display: flex;
      gap: 8px;
    }

    .input-container {
      padding: 16px;
      background-color: var(--vscode-sideBar-background);
      border-top: 1px solid var(--vscode-widget-border);
    }
    
    textarea {
      width: 100%;
      background-color: var(--vscode-input-background);
      color: var(--vscode-input-foreground);
      border: 1px solid var(--vscode-input-border);
      padding: 12px;
      border-radius: 6px;
      font-family: inherit;
      font-size: 13px;
      resize: none;
      outline: none;
      box-sizing: border-box;
      transition: border-color 0.2s;
    }
    
    textarea:focus {
      border-color: var(--vscode-focusBorder);
    }
    
    .controls {
      display: flex;
      justify-content: space-between;
      margin-top: 10px;
    }
    
    button {
      background-color: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      border: none;
      padding: 6px 14px;
      border-radius: 4px;
      cursor: pointer;
      font-weight: 500;
    }
    
    button:hover { background-color: var(--vscode-button-hoverBackground); }
    
    button.secondary {
      background-color: var(--vscode-button-secondaryBackground);
      color: var(--vscode-button-secondaryForeground);
    }
    
    button.secondary:hover { background-color: var(--vscode-button-secondaryHoverBackground); }
    
    button.danger {
      background-color: var(--vscode-errorForeground);
      color: white;
    }
    
    /* Markdown Styles */
    pre {
      background-color: var(--vscode-textCodeBlock-background);
      padding: 12px;
      border-radius: 6px;
      overflow-x: auto;
      margin: 10px 0;
    }
    code { font-family: var(--vscode-editor-font-family); }
  </style>
</head>
<body>

  <div class="header">
    <div style="font-weight: 600;">NimCode AI</div>
    <select id="mode-select" title="Permission Mode">
      <option value="default">Interactive</option>
      <option value="auto">Auto-Safe</option>
      <option value="bypass">Bypass (Auto-Pilot)</option>
    </select>
  </div>

  <div class="chat-container" id="chat">
    <div class="message assistant">
      <p>Hello! I am NimCode, your AI coding assistant.</p>
      <p>How can I help you today?</p>
    </div>
  </div>
  
  <div class="input-container">
    <textarea id="prompt-input" rows="3" placeholder="Ask NimCode to build something... (Shift+Enter for new line)"></textarea>
    <div class="controls">
      <button class="secondary" id="clear-btn">Clear</button>
      <button id="send-btn">Send</button>
    </div>
  </div>

  <script>
    const vscode = acquireVsCodeApi();
    const chat = document.getElementById('chat');
    const input = document.getElementById('prompt-input');
    const sendBtn = document.getElementById('send-btn');
    const clearBtn = document.getElementById('clear-btn');
    const modeSelect = document.getElementById('mode-select');

    // Configure marked with highlight.js
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

    modeSelect.addEventListener('change', (e) => {
      vscode.postMessage({ type: 'set_mode', mode: e.target.value });
    });

    window.addEventListener('message', event => {
      const message = event.data;
      switch (message.type) {
        case 'chunk':
          if (!currentAssistantMessage) {
            currentAssistantMessage = document.createElement('div');
            currentAssistantMessage.className = 'message assistant markdown-body';
            chat.appendChild(currentAssistantMessage);
            rawAssistantContent = "";
          }
          rawAssistantContent += message.content;
          currentAssistantMessage.innerHTML = marked.parse(rawAssistantContent);
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
      header.textContent = '⚙️ Execute Tool: ' + tool;
      
      const argsDisplay = document.createElement('div');
      argsDisplay.className = 'tool-args';
      argsDisplay.textContent = JSON.stringify(args, null, 2);
      
      const actions = document.createElement('div');
      actions.className = 'tool-actions';
      
      const approveBtn = document.createElement('button');
      approveBtn.textContent = 'Approve';
      approveBtn.onclick = () => {
        card.style.opacity = '0.5';
        actions.innerHTML = '<i>Approved</i>';
        vscode.postMessage({ type: 'action_response', granted: true });
      };
      
      const rejectBtn = document.createElement('button');
      rejectBtn.textContent = 'Reject';
      rejectBtn.className = 'danger';
      rejectBtn.onclick = () => {
        card.style.opacity = '0.5';
        actions.innerHTML = '<i style="color:red;">Rejected</i>';
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
    }

    sendBtn.addEventListener('click', sendPrompt);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendPrompt();
      }
    });

    clearBtn.addEventListener('click', () => {
      vscode.postMessage({ type: 'clear' });
      chat.innerHTML = '<div class="message assistant"><p>Context cleared. How can I help?</p></div>';
    });
  </script>
</body>
</html>`;
  }
}
