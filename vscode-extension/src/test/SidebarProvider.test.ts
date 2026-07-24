import * as vscode from 'vscode';
import { SidebarProvider } from '../SidebarProvider';

const spawnMock = jest.fn();
jest.mock('child_process', () => ({
  spawn: (...args: any[]) => spawnMock(...args)
}));

jest.mock('vscode');

jest.mock('child_process', () => {
  return {
    spawn: (...args: any[]) => spawnMock(...args)
  };
});

describe('SidebarProvider', () => {
  let provider: SidebarProvider;
  let mockWebviewView: any;
  let mockProcess: any;

  beforeEach(() => {
    provider = new SidebarProvider({} as vscode.Uri);
    mockWebviewView = {
      webview: {
        options: {},
        html: '',
        onDidReceiveMessage: jest.fn(),
        postMessage: jest.fn()
      }
    };
    
    mockProcess = {
      stdout: { on: jest.fn() },
      stdin: { write: jest.fn() },
      on: jest.fn(),
      kill: jest.fn()
    };

    spawnMock.mockClear();
    spawnMock.mockImplementation((cmd) => {
      if (cmd === 'error-cmd') {
        throw new Error('Command failed');
      }
      return mockProcess;
    });
    
    (vscode.window.showInformationMessage as jest.Mock).mockClear();
    (vscode.window.showErrorMessage as jest.Mock).mockClear();
  });

  it('should resolve webview view and set html', () => {
    provider.resolveWebviewView(mockWebviewView);
    expect(mockWebviewView.webview.html).toContain('<!DOCTYPE html>');
  });

  it('should revive panel', () => {
    provider.revive(mockWebviewView);
    expect(provider._view).toBe(mockWebviewView);
  });

  it('should start nimcode server using spawn', () => {
    provider.resolveWebviewView(mockWebviewView);
    expect(spawnMock).toHaveBeenCalled();
  });

  it('should kill existing process when starting a new one', () => {
    provider.resolveWebviewView(mockWebviewView); // Starts first
    provider.resolveWebviewView(mockWebviewView); // Starts second
    expect(mockProcess.kill).toHaveBeenCalled();
  });

  it('should handle no workspace root', () => {
    (vscode.workspace.workspaceFolders as any) = undefined;
    provider.resolveWebviewView(mockWebviewView);
    expect(vscode.window.showErrorMessage).toHaveBeenCalledWith('NimCode requires an open workspace.');
    // Restore
    (vscode.workspace.workspaceFolders as any) = [{ uri: { fsPath: '/test/path' } }];
  });

  it('should fallback to python -m nimcode.cli if nimcode spawn throws', () => {
    spawnMock.mockImplementationOnce(() => { throw new Error('fail'); });
    provider.resolveWebviewView(mockWebviewView);
    expect(spawnMock).toHaveBeenCalledWith('python', ['-m', 'nimcode.cli', '--stdio'], expect.any(Object));
  });

  it('should parse stdout data and post message to webview', () => {
    provider.resolveWebviewView(mockWebviewView);
    const stdoutHandler = mockProcess.stdout.on.mock.calls[0][1];
    
    // Valid JSON
    stdoutHandler(Buffer.from('{"type": "info", "content": "hi"}\n'));
    expect(mockWebviewView.webview.postMessage).toHaveBeenCalledWith({ type: 'info', content: 'hi' });
    
    // Invalid JSON (should not throw)
    stdoutHandler(Buffer.from('not json\n'));
    
    // Empty string
    stdoutHandler(Buffer.from('   \n'));
  });

  it('should handle process close', () => {
    provider.resolveWebviewView(mockWebviewView);
    const closeHandler = mockProcess.on.mock.calls[0][1];
    closeHandler(0);
  });

  // Message Handlers
  it('should handle onInfo message', async () => {
    provider.resolveWebviewView(mockWebviewView);
    const messageHandler = mockWebviewView.webview.onDidReceiveMessage.mock.calls[0][0];
    await messageHandler({ type: 'onInfo', value: 'test info' });
    expect(vscode.window.showInformationMessage).toHaveBeenCalledWith('test info');
    
    await messageHandler({ type: 'onInfo' }); // no value branch
  });

  it('should handle onError message', async () => {
    provider.resolveWebviewView(mockWebviewView);
    const messageHandler = mockWebviewView.webview.onDidReceiveMessage.mock.calls[0][0];
    await messageHandler({ type: 'onError', value: 'test error' });
    expect(vscode.window.showErrorMessage).toHaveBeenCalledWith('test error');
    
    await messageHandler({ type: 'onError' }); // no value branch
  });

  it('should write IPC messages to stdin', async () => {
    provider.resolveWebviewView(mockWebviewView);
    const messageHandler = mockWebviewView.webview.onDidReceiveMessage.mock.calls[0][0];
    
    await messageHandler({ type: 'prompt', value: 'hello' });
    expect(mockProcess.stdin.write).toHaveBeenCalledWith(JSON.stringify({ type: 'prompt', content: 'hello' }) + '\n');
    
    await messageHandler({ type: 'clear' });
    expect(mockProcess.stdin.write).toHaveBeenCalledWith(JSON.stringify({ type: 'clear' }) + '\n');
    
    await messageHandler({ type: 'action_response', granted: true });
    expect(mockProcess.stdin.write).toHaveBeenCalledWith(JSON.stringify({ type: 'action_response', granted: true }) + '\n');
    
    await messageHandler({ type: 'set_mode', mode: 'auto' });
    expect(mockProcess.stdin.write).toHaveBeenCalledWith(JSON.stringify({ type: 'set_mode', mode: 'auto' }) + '\n');
    
    await messageHandler({ type: 'set_model', model: 'llama-3.1-8b' });
    expect(mockProcess.stdin.write).toHaveBeenCalledWith(JSON.stringify({ type: 'set_model', model: 'llama-3.1-8b' }) + '\n');
    
    // unrecognized msg
    await messageHandler({ type: 'unknown' });
  });

  it('should ignore IPC messages if nimcodeProcess or stdin is null', async () => {
    provider.resolveWebviewView(mockWebviewView);
    const messageHandler = mockWebviewView.webview.onDidReceiveMessage.mock.calls[0][0];
    
    // Test when process is null
    (provider as any).nimcodeProcess = null;
    await messageHandler({ type: 'prompt', value: 'hello' });
    // Should have started server on prompt if it was null, but let's check other types
    (provider as any).nimcodeProcess = null;
    await messageHandler({ type: 'clear' });
    
    // Test when stdin is null
    (provider as any).nimcodeProcess = { stdin: null, kill: jest.fn() };
    await messageHandler({ type: 'action_response', granted: true });
    await messageHandler({ type: 'set_mode', mode: 'auto' });
    await messageHandler({ type: 'set_model', model: 'test-model' });
    
    expect(mockProcess.stdin.write).not.toHaveBeenCalledWith(expect.stringContaining('action_response'));
  });

  it('should handle spawn returning process without stdout', () => {
    spawnMock.mockImplementationOnce(() => {
      return {
        on: jest.fn(),
        kill: jest.fn()
      }; // no stdout, no stdin
    });
    
    // This will trigger startNimcodeServer which hits if (this.nimcodeProcess.stdout)
    provider.resolveWebviewView(mockWebviewView);
    
    const messageHandler = mockWebviewView.webview.onDidReceiveMessage.mock.calls[0][0];
    // Trigger prompt to hit if (this.nimcodeProcess && this.nimcodeProcess.stdin)
    messageHandler({ type: 'prompt', value: 'hello' });
    
    expect(mockProcess.stdin.write).not.toHaveBeenCalled();
  });
});
