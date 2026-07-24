import * as vscode from 'vscode';
import { ChatPanel } from './ChatPanel';

export function activate(context: vscode.ExtensionContext) {
  console.log('NimCode extension activated!');
  
  let disposable = vscode.commands.registerCommand('nimcode.startChat', () => {
    ChatPanel.render(context.extensionUri);
  });
  
  context.subscriptions.push(disposable);
}

export function deactivate() {}
