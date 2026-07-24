import * as vscode from 'vscode';
import { activate } from '../extension';

jest.mock('vscode');

describe('Extension Activation', () => {
  it('should register SessionProvider and commands', () => {
    const context: any = {
      extensionUri: {},
      subscriptions: {
        push: jest.fn()
      }
    };
    
    // Setup mock workspace root
    (vscode.workspace as any).workspaceFolders = [{ uri: { fsPath: '/test/path' } }];
    
    activate(context);
    
    expect(vscode.window.registerTreeDataProvider).toHaveBeenCalledWith(
      "nimcode.sessionsView",
      expect.anything()
    );
    
    expect(vscode.commands.registerCommand).toHaveBeenCalledWith(
      "nimcode.newChat",
      expect.anything()
    );
    
    expect(context.subscriptions.push).toHaveBeenCalledTimes(4); // 4 commands registered
  });
  
  it('should not throw on deactivate', () => {
    const { deactivate } = require('../extension');
    expect(() => deactivate()).not.toThrow();
  });
});
