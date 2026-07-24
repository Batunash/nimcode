import * as vscode from 'vscode';
import { activate } from '../extension';

jest.mock('vscode');

describe('Extension Activation', () => {
  it('should register SidebarProvider and command', () => {
    const context: any = {
      extensionUri: {},
      subscriptions: {
        push: jest.fn()
      }
    };
    
    activate(context);
    
    expect(vscode.window.registerWebviewViewProvider).toHaveBeenCalledWith(
      "nimcode.chatView",
      expect.anything()
    );
    
    expect(vscode.commands.registerCommand).toHaveBeenCalledWith(
      "nimcode.startChat",
      expect.anything()
    );
    
    expect(context.subscriptions.push).toHaveBeenCalledTimes(2);
  });
  
  it('should execute chatView.focus when startChat is called', () => {
    const context: any = {
      extensionUri: {},
      subscriptions: { push: jest.fn() }
    };
    
    activate(context);
    
    const startChatCommand = (vscode.commands.registerCommand as jest.Mock).mock.calls[0][1];
    startChatCommand();
    
    expect(vscode.commands.executeCommand).toHaveBeenCalledWith('nimcode.chatView.focus');
  });
  
  it('should not throw on deactivate', () => {
    const { deactivate } = require('../extension');
    expect(() => deactivate()).not.toThrow();
  });
});
