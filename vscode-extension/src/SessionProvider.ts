import * as vscode from 'vscode';
import * as path from 'path';

export class SessionProvider implements vscode.TreeDataProvider<SessionItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<SessionItem | undefined | void> = new vscode.EventEmitter<SessionItem | undefined | void>();
    readonly onDidChangeTreeData: vscode.Event<SessionItem | undefined | void> = this._onDidChangeTreeData.event;

    // In a real implementation, these would be loaded from disk/workspace state
    private sessions: SessionItem[] = [];

    constructor(private workspaceRoot: string | undefined) {
        // Dummy data for now. We can enhance this to read from a local directory or globalState.
        this.sessions = [
            new SessionItem("Current Session", "default", vscode.TreeItemCollapsibleState.None)
        ];
    }

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }

    getTreeItem(element: SessionItem): vscode.TreeItem {
        return element;
    }

    getChildren(element?: SessionItem): Thenable<SessionItem[]> {
        if (!this.workspaceRoot) {
            vscode.window.showInformationMessage('No dependency in empty workspace');
            return Promise.resolve([]);
        }

        if (element) {
            return Promise.resolve([]);
        } else {
            return Promise.resolve(this.sessions);
        }
    }
    
    addSession(name: string, id: string) {
        this.sessions.unshift(new SessionItem(name, id, vscode.TreeItemCollapsibleState.None));
        this.refresh();
    }
    
    deleteSession(id: string) {
        this.sessions = this.sessions.filter(s => s.sessionId !== id);
        this.refresh();
    }
}

export class SessionItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly sessionId: string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState
    ) {
        super(label, collapsibleState);
        this.tooltip = `Session: ${this.label}`;
        this.description = this.sessionId === "default" ? "Active" : "";
        
        this.command = {
            command: 'nimcode.openSession',
            title: 'Open Session',
            arguments: [this]
        };
    }

    iconPath = new vscode.ThemeIcon('comment-discussion');
}
