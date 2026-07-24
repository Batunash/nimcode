import * as vscode from 'vscode';
import { SidebarProvider } from './SidebarProvider';

export function activate(context: vscode.ExtensionContext) {
  console.log('NimCode extension activated!');

  const sidebarProvider = new SidebarProvider(context.extensionUri);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(
      "nimcode.chatView",
      sidebarProvider
    )
  );

  let disposable = vscode.commands.registerCommand('nimcode.startChat', () => {
    vscode.commands.executeCommand('nimcode.chatView.focus');
  });
  
  context.subscriptions.push(disposable);
}

export function deactivate() {}
