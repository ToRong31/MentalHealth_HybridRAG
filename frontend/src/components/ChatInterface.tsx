import React, { useEffect, useRef, useState } from 'react';
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
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  const [isNearBottom, setIsNearBottom] = useState(true);

  const scrollToBottom = (behavior: ScrollBehavior = 'smooth') => {
    messagesEndRef.current?.scrollIntoView({ behavior });
  };

  // detect user scroll position
  useEffect(() => {
    const el = messagesContainerRef.current;
    if (!el) return;

    const onScroll = () => {
      const threshold = 80; // px
      const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
      setIsNearBottom(distanceFromBottom < threshold);
    };

    onScroll();
    el.addEventListener('scroll', onScroll, { passive: true });
    return () => el.removeEventListener('scroll', onScroll);
  }, []);

  // ✅ Only autoscroll when appropriate
  const prevLenRef = useRef<number>(messages.length);

  useEffect(() => {
    const prevLen = prevLenRef.current;
    const lenIncreased = messages.length > prevLen;

    // Scroll if user is near bottom and new messages arrive
    if (lenIncreased && isNearBottom) {
      scrollToBottom('smooth');
    }

    prevLenRef.current = messages.length;
  }, [messages, isNearBottom]);

  const hasMessages = messages.length > 0;

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSendMessage();
    }
  };

  return (
    <div className={`chat-surface ${hasMessages ? 'has-messages' : 'is-empty'}`}>
      <div className="chat-messages" ref={messagesContainerRef}>
        {messages.length === 0 && !currentConversationTitle && (
          <div className="welcome-message">
            <img
              src="https://res.cloudinary.com/dranb4kom/image/upload/v1765210560/Logo_tjch5z.svg"
              alt="MenChat logo"
              className="welcome-logo"
            />
            <h2>Bạn đang gặp vấn đề gì?</h2>
            <p>Hãy chia sẻ, MenChat sẽ hỗ trợ bạn.</p>
          </div>
        )}

        {messages.map((message) => (
          <div
            key={message.tempId || message.id} // ✅ Use tempId for pending, id for committed
            className={`message ${message.sender === 'user' ? 'message-user' : 'message-bot'} ${
              message.is_high_risk ? 'message-high-risk' : ''
            } ${message.isPending ? 'message-pending' : ''}`}
          >
            <div className="message-content">
              <div className="message-text">
                {message.content}
                {message.isPending && (
                  <span className="pending-indicator" title="Đang gửi..."></span>
                )}
              </div>
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
            onKeyDown={handleKeyDown} // ✅ use keyDown
            disabled={false} // ✅ IMPORTANT: không disable input chỉ vì isLoading (để đổi chat/gõ tiếp)
          />
          <button
            className="send-button"
            onClick={onSendMessage}
            disabled={!inputValue.trim()} // ✅ không disable vì isLoading
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
    </div>
  );
};

export default ChatInterface;
