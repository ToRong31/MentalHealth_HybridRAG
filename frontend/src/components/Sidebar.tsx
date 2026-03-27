import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import type { Conversation } from '../types';

interface SidebarProps {
    conversations: Conversation[];
    currentConversationId: number | undefined;
    isOpen: boolean;
    onToggle: () => void;
    onNewConversation: () => void;
    onSelectConversation: (id: number) => void;
    onRenameConversation: (id: number, newTitle: string) => void;
    onDeleteConversation: (id: number) => void;
}

const Sidebar: React.FC<SidebarProps> = ({
    conversations,
    currentConversationId,
    isOpen,
    onToggle,
    onNewConversation,
    onSelectConversation,
    onRenameConversation,
    onDeleteConversation,
}) => {
    const { user, logout } = useAuth();
    const [openMenuId, setOpenMenuId] = useState<number | null>(null);
    const [renamingId, setRenamingId] = useState<number | null>(null);
    const [renameValue, setRenameValue] = useState('');
    const menuRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    // Close menu when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
                setOpenMenuId(null);
            }
        };

        if (openMenuId !== null) {
            document.addEventListener('mousedown', handleClickOutside);
        }

        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, [openMenuId]);

    // Focus input when entering rename mode
    useEffect(() => {
        if (renamingId !== null && inputRef.current) {
            inputRef.current.focus();
            inputRef.current.select();
        }
    }, [renamingId]);

    const handleRenameClick = (conv: Conversation, e: React.MouseEvent) => {
        e.stopPropagation();
        setRenamingId(conv.id);
        setRenameValue(conv.title);
        setOpenMenuId(null);
    };

    const handleRenameSubmit = (id: number) => {
        if (renameValue.trim() && renameValue !== conversations.find(c => c.id === id)?.title) {
            onRenameConversation(id, renameValue.trim());
        }
        setRenamingId(null);
        setRenameValue('');
    };

    const handleRenameCancel = () => {
        setRenamingId(null);
        setRenameValue('');
    };

    const handleDeleteClick = (id: number, e: React.MouseEvent) => {
        e.stopPropagation();
        onDeleteConversation(id);
        setOpenMenuId(null);
    };

    return (
        <div className={`sidebar ${isOpen ? 'open' : 'closed'}`}>
            <div className="sidebar-header">
                <div 
                    className={`brand ${!isOpen ? 'brand-clickable' : ''}`}
                    onClick={!isOpen ? onToggle : undefined}
                    title={!isOpen ? "Mở rộng thanh bên" : undefined}
                >
                    <img
                        src="https://res.cloudinary.com/dranb4kom/image/upload/v1765210560/Logo_tjch5z.svg"
                        alt="MenChat logo"
                        className="brand-logo"
                    />
                    <div className="brand-text">
                        <span className="brand-name">MenChat</span>
                        <span className="brand-sub">Cuộc trò chuyện</span>
                    </div>
                    {!isOpen && (
                        <div className="brand-expand-arrow">▶</div>
                    )}
                </div>
                <button className="btn-icon" onClick={onToggle}>
                    {isOpen ? '◀' : '▶'}
                </button>
            </div>

            <button className="btn-new-chat" onClick={onNewConversation}>
                <svg className="btn-chat-icon" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 20h9"></path>
                    <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
                </svg>
                <span className="btn-text">Đoạn chat mới</span>
            </button>

            <div className="conversation-list">
                {conversations.map((conv) => (
                    <div
                        key={conv.id}
                        className={`conversation-item ${currentConversationId === conv.id ? 'active' : ''}`}
                        onClick={() => onSelectConversation(conv.id)}
                        style={{ zIndex: openMenuId === conv.id ? 1001 : 'auto' }}
                    >
                        {renamingId === conv.id ? (
                            <input
                                ref={inputRef}
                                type="text"
                                className="conversation-rename-input"
                                value={renameValue}
                                onChange={(e) => setRenameValue(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter') {
                                        handleRenameSubmit(conv.id);
                                    } else if (e.key === 'Escape') {
                                        handleRenameCancel();
                                    }
                                }}
                                onBlur={() => handleRenameSubmit(conv.id)}
                                onClick={(e) => e.stopPropagation()}
                            />
                        ) : (
                            <>
                                <div className="conversation-title">{conv.title}</div>
                                <div className="conversation-date">
                                    {new Date(conv.updated_at).toLocaleDateString()}
                                </div>
                            </>
                        )}
                        <button
                            className="btn-menu"
                            onClick={(e) => {
                                e.stopPropagation();
                                setOpenMenuId(openMenuId === conv.id ? null : conv.id);
                            }}
                            aria-label="Tùy chọn"
                        >
                            ⋮
                        </button>
                        {openMenuId === conv.id && (
                            <div ref={menuRef} className="conversation-menu" onClick={(e) => e.stopPropagation()}>
                                <button
                                    className="menu-item"
                                    onClick={(e) => handleRenameClick(conv, e)}
                                >
                                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M12 20h9"></path>
                                        <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
                                    </svg>
                                    Đổi tên
                                </button>
                                <button
                                    className="menu-item menu-item-danger"
                                    onClick={(e) => handleDeleteClick(conv.id, e)}
                                >
                                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <polyline points="3 6 5 6 21 6"></polyline>
                                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                                    </svg>
                                    Xóa
                                </button>
                            </div>
                        )}
                    </div>
                ))}
            </div>

            <div className="sidebar-footer">
                <div className="user-info">
                    <span>{user?.username}</span>
                </div>
                <button className="btn-logout" onClick={logout}>
                    Đăng xuất
                </button>
            </div>
        </div>
    );
};

export default Sidebar;
