class TreeItem {
  label: string;
  collapsibleState: any;
  constructor(label: string, collapsibleState: any) {
    this.label = label;
    this.collapsibleState = collapsibleState;
  }
}

class ThemeIcon {
  constructor(public id: string) {}
}

class EventEmitter {
  event = jest.fn();
  fire = jest.fn();
}

const vscode = {
  TreeItem,
  ThemeIcon,
  EventEmitter,
  TreeItemCollapsibleState: { None: 0 },
  window: {
    registerWebviewViewProvider: jest.fn(),
    registerTreeDataProvider: jest.fn(),
    showInformationMessage: jest.fn(),
    showErrorMessage: jest.fn(),
    createWebviewPanel: jest.fn(() => ({
      webview: { html: '', onDidReceiveMessage: jest.fn(), postMessage: jest.fn() },
      onDidDispose: jest.fn(),
      reveal: jest.fn()
    }))
  },
  workspace: {
    workspaceFolders: [{
      uri: { fsPath: '/test/path' }
    }]
  },
  commands: {
    registerCommand: jest.fn(),
    executeCommand: jest.fn()
  },
  Uri: {
    file: jest.fn(),
    joinPath: jest.fn((uri, ...pathSegments) => {
      return { path: '/test/path/' + pathSegments.join('/') };
    })
  },
  ViewColumn: {
    One: 1
  }
};

module.exports = vscode;
