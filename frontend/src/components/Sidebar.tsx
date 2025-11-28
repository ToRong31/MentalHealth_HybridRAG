import React from 'react';
import { useAuth } from '../context/AuthContext';
import type { Conversation } from '../types';

interface SidebarProps {
    conversations: Conversation[];
    currentConversationId: number | undefined;
    isOpen: boolean;
    onToggle: () => void;
    onNewConversation: () => void;
    onSelectConversation: (id: number) => void;
    onDeleteConversation: (id: number) => void;
}

const Sidebar: React.FC<SidebarProps> = ({
    conversations,
    currentConversationId,
    isOpen,
    onToggle,
    onNewConversation,
    onSelectConversation,
    onDeleteConversation,
}) => {
    const { user, logout } = useAuth();

    return (
        <div className={`sidebar ${isOpen ? 'open' : 'closed'}`}>
            <div className="sidebar-header">
                <h2>💚 Conversations</h2>
                <button className="btn-icon" onClick={onToggle}>
                    {isOpen ? '◀' : '▶'}
                </button>
            </div>

            <button className="btn-new-chat" onClick={onNewConversation}>
                + New Conversation
            </button>

            <div className="conversation-list">
                {conversations.map((conv) => (
                    <div
                        key={conv.id}
                        className={`conversation-item ${currentConversationId === conv.id ? 'active' : ''}`}
                        onClick={() => onSelectConversation(conv.id)}
                    >
                        <div className="conversation-title">{conv.title}</div>
                        <div className="conversation-date">
                            {new Date(conv.updated_at).toLocaleDateString()}
                        </div>
                        <button
                            className="btn-delete"
                            onClick={(e) => {
                                e.stopPropagation();
                                onDeleteConversation(conv.id);
                            }}
                        >
                            🗑️
                        </button>
                    </div>
                ))}
            </div>

            <div className="sidebar-footer">
                <div className="user-info">
                    <span>{user?.username}</span>
                </div>
                <button className="btn-logout" onClick={logout}>
                    Logout
                </button>
            </div>
        </div>
    );
};

export default Sidebar;
