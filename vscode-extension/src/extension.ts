import * as vscode from 'vscode';
import { SessionProvider, SessionItem } from './SessionProvider';
import { ChatPanel } from './ChatPanel';

export function activate(context: vscode.ExtensionContext) {
  console.log('NimCode extension activated!');

  const workspaceRoot = vscode.workspace.workspaceFolders?.[0].uri.fsPath;
  const sessionProvider = new SessionProvider(workspaceRoot);
  
  vscode.window.registerTreeDataProvider('nimcode.sessionsView', sessionProvider);

  context.subscriptions.push(
    vscode.commands.registerCommand('nimcode.newChat', () => {
      const sessionId = "session-" + Date.now();
      sessionProvider.addSession("New Chat", sessionId);
      ChatPanel.render(context.extensionUri, sessionId);
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('nimcode.openSession', (item: SessionItem) => {
      ChatPanel.render(context.extensionUri, item.sessionId);
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('nimcode.deleteSession', (item: SessionItem) => {
      sessionProvider.deleteSession(item.sessionId);
    })
  );
  
  // Start the default session immediately if they run the old command
  context.subscriptions.push(
    vscode.commands.registerCommand('nimcode.startChat', () => {
      vscode.commands.executeCommand('nimcode.newChat');
    })
  );
}

export function deactivate() {}
