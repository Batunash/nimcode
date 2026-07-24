import * as vscode from 'vscode';
import { spawn, ChildProcess } from 'child_process';
import * as path from 'path';

export class SidebarProvider implements vscode.WebviewViewProvider {
  _view?: vscode.WebviewView;
  _doc?: vscode.TextDocument;
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
          if (!data.value) {
            return;
          }
          vscode.window.showInformationMessage(data.value);
          break;
        }
        case 'onError': {
          if (!data.value) {
            return;
          }
          vscode.window.showErrorMessage(data.value);
          break;
        }
        case 'prompt': {
          // Send prompt to Python backend
          if (!this.nimcodeProcess) {
            this.startNimcodeServer();
          }
          
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
      }
    });

    // Automatically start the server when the view is resolved
    this.startNimcodeServer();
  }

  public revive(panel: vscode.WebviewView) {
    this._view = panel;
  }

  private startNimcodeServer() {
    if (this.nimcodeProcess) {
      this.nimcodeProcess.kill();
    }
    
    // We expect nimcode to be runnable via python -m nimcode from the workspace root or installed globally
    // For development, we'll try to run the local module
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0].uri.fsPath;
    if (!workspaceRoot) {
        vscode.window.showErrorMessage('NimCode requires an open workspace.');
        return;
    }

    try {
        this.nimcodeProcess = spawn('nimcode', ['--stdio'], { cwd: workspaceRoot });
    } catch (e) {
        // Fallback to python module if nimcode is not in PATH
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
            console.error('Failed to parse NimCode STDOUT:', line);
          }
        }
      });
    }

    if (this.nimcodeProcess.stderr) {
      this.nimcodeProcess.stderr.on('data', (data) => {
        console.error(`NimCode STDERR: ${data}`);
      });
    }

    this.nimcodeProcess.on('close', (code) => {
      console.log(`NimCode process exited with code ${code}`);
      this.nimcodeProcess = null;
    });
  }

  private _getHtmlForWebview(webview: vscode.Webview) {
    // We will build a sleek Claude-like UI using VS Code theme variables
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NimCode Chat</title>
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
      padding: 12px;
      border-radius: 8px;
      line-height: 1.5;
      font-size: 14px;
      max-width: 90%;
    }
    .message.user {
      align-self: flex-end;
      background-color: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
    }
    .message.assistant {
      align-self: flex-start;
      background-color: var(--vscode-editorWidget-background);
      border: 1px solid var(--vscode-widget-border);
    }
    .message.status {
      align-self: center;
      font-style: italic;
      color: var(--vscode-descriptionForeground);
      background: none;
      border: none;
      padding: 4px;
    }
    .input-container {
      padding: 16px;
      background-color: var(--vscode-editor-background);
      border-top: 1px solid var(--vscode-widget-border);
      position: sticky;
      bottom: 0;
    }
    textarea {
      width: 100%;
      background-color: var(--vscode-input-background);
      color: var(--vscode-input-foreground);
      border: 1px solid var(--vscode-input-border);
      padding: 12px;
      border-radius: 6px;
      font-family: inherit;
      resize: none;
      outline: none;
      box-sizing: border-box;
    }
    textarea:focus {
      border-color: var(--vscode-focusBorder);
    }
    .controls {
      display: flex;
      justify-content: space-between;
      margin-top: 8px;
    }
    button {
      background-color: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      border: none;
      padding: 6px 12px;
      border-radius: 4px;
      cursor: pointer;
    }
    button:hover {
      background-color: var(--vscode-button-hoverBackground);
    }
    button.secondary {
      background-color: var(--vscode-button-secondaryBackground);
      color: var(--vscode-button-secondaryForeground);
    }
    button.secondary:hover {
      background-color: var(--vscode-button-secondaryHoverBackground);
    }
    pre {
      background-color: var(--vscode-textCodeBlock-background);
      padding: 8px;
      border-radius: 4px;
      overflow-x: auto;
    }
    code {
      font-family: var(--vscode-editor-font-family);
    }
  </style>
</head>
<body>
  <div class="chat-container" id="chat">
    <div class="message assistant">Hello! I am NimCode, your AI coding assistant. How can I help you today?</div>
  </div>
  
  <div class="input-container">
    <textarea id="prompt-input" rows="3" placeholder="Ask NimCode to build something..."></textarea>
    <div class="controls">
      <button class="secondary" id="clear-btn">Clear Context</button>
      <button id="send-btn">Send</button>
    </div>
  </div>

  <script>
    const vscode = acquireVsCodeApi();
    const chat = document.getElementById('chat');
    const input = document.getElementById('prompt-input');
    const sendBtn = document.getElementById('send-btn');
    const clearBtn = document.getElementById('clear-btn');

    let currentAssistantMessage = null;

    // Handle incoming messages from the extension
    window.addEventListener('message', event => {
      const message = event.data;
      switch (message.type) {
        case 'info':
        case 'status':
          // Optional status tracking
          console.log(message.content);
          break;
        case 'chunk':
          if (!currentAssistantMessage) {
            currentAssistantMessage = document.createElement('div');
            currentAssistantMessage.className = 'message assistant';
            chat.appendChild(currentAssistantMessage);
          }
          currentAssistantMessage.textContent += message.content;
          chat.scrollTop = chat.scrollHeight;
          break;
        case 'done':
          currentAssistantMessage = null;
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

    function sendPrompt() {
      const text = input.value.trim();
      if (!text) return;
      
      // Add user message to UI
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
      chat.innerHTML = '<div class="message assistant">Context cleared. How can I help?</div>';
    });
  </script>
</body>
</html>`;
  }
}
