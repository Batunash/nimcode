import * as vscode from 'vscode';
export function activate(context: vscode.ExtensionContext) {
  console.log('NimCode extension activated!');
  let disposable = vscode.commands.registerCommand('nimcode.helloWorld', () => {
    vscode.window.showInformationMessage('Hello from NimCode!');
  });
  context.subscriptions.push(disposable);
}
export function deactivate() {}
