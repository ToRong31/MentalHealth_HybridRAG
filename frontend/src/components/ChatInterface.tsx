import React, { useRef, useEffect } from 'react';
import type { Message } from '../types';

interface ChatInterfaceProps {
    messages: Message[];
    inputValue: string;
    isLoading: boolean;
    currentConversationTitle?: string;
    onInputChange: (value: string) => void;
    onSendMessage: () => void;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({
    messages,
    inputValue,
    isLoading,
    currentConversationTitle,
    onInputChange,
    onSendMessage,
}) => {
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            onSendMessage();
        }
    };

    return (
        <>
            <div className="chat-messages">
                {messages.length === 0 && !currentConversationTitle && (
                    <div className="welcome-message">
                        <h2>Welcome to Mental Health Support! 💚</h2>
                        <p>Start a new conversation to begin chatting</p>
                    </div>
                )}

                {messages.map((message) => (
                    <div
                        key={message.id}
                        className={`message ${message.sender === 'user' ? 'message-user' : 'message-bot'} ${message.is_high_risk ? 'message-high-risk' : ''
                            }`}
                    >
                        <div className="message-content">
                            <div className="message-text">{message.content}</div>
                            <div className="message-time">
                                {new Date(message.created_at).toLocaleTimeString([], {
                                    hour: '2-digit',
                                    minute: '2-digit',
                                })}
                            </div>
                        </div>
                    </div>
                ))}

                {isLoading && (
                    <div className="message message-bot">
                        <div className="message-content">
                            <div className="typing-indicator">
                                <span></span>
                                <span></span>
                                <span></span>
                            </div>
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            <div className="chat-input-container">
                <div className="chat-input-wrapper">
                    <input
                        type="text"
                        className="chat-input"
                        placeholder="Type your message here..."
                        value={inputValue}
                        onChange={(e) => onInputChange(e.target.value)}
                        onKeyPress={handleKeyPress}
                        disabled={isLoading}
                    />
                    <button
                        className="send-button"
                        onClick={onSendMessage}
                        disabled={isLoading || !inputValue.trim()}
                    >
                        <svg
                            xmlns="http://www.w3.org/2000/svg"
                            width="24"
                            height="24"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                        >
                            <line x1="22" y1="2" x2="11" y2="13"></line>
                            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                        </svg>
                    </button>
                </div>
            </div>
        </>
    );
};

export default ChatInterface;
