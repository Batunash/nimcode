import * as vscode from 'vscode';
import { SessionProvider, SessionItem } from '../../src/SessionProvider';

jest.mock('vscode');

describe('SessionProvider Test Suite', () => {
    it('should instantiate SessionProvider', () => {
        const provider = new SessionProvider('dummy-root');
        expect(provider).toBeDefined();
    });

    it('should create SessionItem', () => {
        const item = new SessionItem('Test Session', 'session-123', 0); // 0 is None
        expect(item.label).toBe('Test Session');
        expect(item.sessionId).toBe('session-123');
    });

    it('should add and delete sessions', async () => {
        const provider = new SessionProvider('dummy-root');
        provider.addSession('New Session', 'session-new');
        
        let children = await provider.getChildren();
        expect(children.length).toBe(2);
        
        provider.deleteSession('session-new');
        children = await provider.getChildren();
        expect(children.length).toBe(1);
    });
});
