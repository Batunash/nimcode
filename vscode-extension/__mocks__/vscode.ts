const vscode = {
  window: {
    registerWebviewViewProvider: jest.fn(),
    showInformationMessage: jest.fn(),
    showErrorMessage: jest.fn()
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
    joinPath: jest.fn((uri, ...pathSegments) => {
      return { path: '/test/path/' + pathSegments.join('/') };
    })
  }
};

module.exports = vscode;
