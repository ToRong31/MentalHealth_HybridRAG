import React, { useState, useEffect, useRef, useCallback } from 'react';
import { ChatSidebar } from '../components/ChatSidebar';
import { ChatMessage, type Message } from '../components/ChatMessage';
import { ChatComposer } from '../components/ChatComposer';
import { EmptyState } from '../components/EmptyState';
import { Menu, Bot } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import {
  getConversations,
  getConversation,
  updateConversation,
  deleteConversation,
  sendMessage,
} from '../services/api';
import type { Conversation } from '../types';

// Per-conversation state management
interface ConversationState {
  messages: Message[];
  inputDraft: string;
  pendingCount: number;
  serverMessages: Message[]; // Messages from server (for reconciliation)
}

const Home: React.FC = () => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<number | null>(null);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { user, logout } = useAuth();
  
  // Force re-render trigger
  const [, setRenderTrigger] = useState(0);
  const forceUpdate = useCallback(() => setRenderTrigger(prev => prev + 1), []);

  // Store state per conversation (key = conversationId string, or 'new' for new conversation)
  const conversationStatesRef = useRef<Map<string, ConversationState>>(new Map());
  
  // Track pending requests by tempId to handle responses correctly
  const pendingRequestsRef = useRef<Map<string, { conversationKey: string; userTempId: string }>>(new Map());

  // Get conversation key
  const getConversationKey = (convId: number | null): string => {
    return convId === null ? 'new' : convId.toString();
  };

  // Get or initialize conversation state
  const getConversationState = useCallback((convKey: string): ConversationState => {
    if (!conversationStatesRef.current.has(convKey)) {
      conversationStatesRef.current.set(convKey, {
        messages: [],
        inputDraft: '',
        pendingCount: 0,
        serverMessages: [],
      });
    }
    return conversationStatesRef.current.get(convKey)!;
  }, []);

  // Update conversation state
  const updateConversationState = useCallback((convKey: string, updates: Partial<ConversationState>) => {
    const current = getConversationState(convKey);
    conversationStatesRef.current.set(convKey, { ...current, ...updates });
  }, [getConversationState]);

  // Merge server messages with pending messages
  const mergeMessages = useCallback((serverMessages: Message[], pendingMessages: Message[]): Message[] => {
    const serverMap = new Map(serverMessages.map(m => [m.id, m]));
    const merged: Message[] = [...serverMessages];

    // Add pending messages that don't exist in server messages
    pendingMessages.forEach(pm => {
      if (pm.isPending && !serverMap.has(pm.id)) {
        merged.push(pm);
      }
    });

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [currentState?.messages]);

    return merged.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
  }, []);

  useEffect(() => {
    loadConversations();
  }, []);

  const loadConversations = async () => {
    try {
      const convs = await getConversations();
      setConversations(convs);
    } catch (error) {
      console.error('Error loading conversations:', error);
    }
  };

  const handleNewConversation = () => {
    setCurrentConversationId(null);
    // Don't clear the 'new' conversation state - it should persist
  };

  const handleSelectConversation = async (conversationId: number) => {
    try {
      const convKey = getConversationKey(conversationId);
      const state = getConversationState(convKey);

      // If we haven't loaded this conversation yet, fetch from server
      if (state.serverMessages.length === 0 && state.pendingCount === 0) {
        const conversation = await getConversation(conversationId);
        const mergedMessages = mergeMessages(conversation.messages, state.messages);
        
        updateConversationState(convKey, {
          serverMessages: conversation.messages,
          messages: mergedMessages,
        });
      }

      setCurrentConversationId(conversationId);
    } catch (error) {
      console.error('Error loading conversation:', error);
    }
  };

  const handleRenameConversation = async (conversationId: number, newTitle: string) => {
    try {
      const updatedConv = await updateConversation(conversationId, newTitle);
      setConversations(conversations.map((c) => (c.id === conversationId ? updatedConv : c)));
    } catch (error) {
      console.error('Error renaming conversation:', error);
    }
  };

  const handleDeleteConversation = async (conversationId: number) => {
    if (!confirm('Bạn có chắc chắn muốn xóa đoạn chat này?')) return;

    try {
      await deleteConversation(conversationId);
      setConversations(conversations.filter((c) => c.id !== conversationId));

      // Clean up state
      const convKey = getConversationKey(conversationId);
      conversationStatesRef.current.delete(convKey);

      // If deleting current conversation, switch to new
      if (currentConversationId === conversationId) {
        setCurrentConversationId(null);
      }
    } catch (error) {message?: string) => {
    const convKey = getConversationKey(currentConversationId);
    const state = getConversationState(convKey);
    const userMessageContent = (message || state.inputDraft).trim();

    if (!userMessageContent) return;

    // Show typing indicator
    setIsTyping(true)) => {
    const convKey = getConversationKey(currentConversationId);
    const state = getConversationState(convKey);
    const userMessageContent = state.inputDraft.trim();

    if (!userMessageContent) return;

    // Generate unique IDs for this message pair
    const tempId = `temp-${Date.now()}-${Math.random()}`;
    const userTempId = `user-${tempId}`;
    const now = new Date().toISOString();
    
    // Nếu đang ở conversation mới và chưa có conversation nào, tạo placeholder
    const isNewConversation = currentConversationId === null;
    let workingConversationId = currentConversationId;
    
    if (isNewConversation) {
      // Tạo conversation placeholder trong danh sách
      const placeholderConv: Conversation = {
        id: -Date.now(), // Temporary negative ID
        user_id: 0,
        title: `Chat ${new Date().toLocaleTimeString()}`,
        created_at: now,
        updated_at: now,
      };
      setConversations(prev => [placeholderConv, ...prev]);
      workingConversationId = placeholderConv.id;
      setCurrentConversationId(workingConversationId);
    }

    // Create pending user message
    const pendingUserMessage: Message = {
      id: Date.now(), // Temporary ID
      conversation_id: workingConversationId ?? 0,
      content: userMessageContent,
      sender: 'user',
      is_high_risk: false,
      is_mental_health_related: true,
      created_at: now,
      isPending: true,
      tempId: userTempId,
    };

    // Update state: add pending message, clear input, increment pending count
    const workingConvKey = getConversationKey(workingConversationId);
    const workingState = getConversationState(workingConvKey);
    const updatedMessages = [...workingState.messages, pendingUserMessage];
    updateConversationState(workingConvKey, {
      messages: updatedMessages,
      inputDraft: '',
      pendingCount: workingState.pendingCount + 1,
    });

    forceUpdate();

    // Track this request
    pendingRequestsRef.current.set(tempId, { conversationKey: workingConvKey, userTempId });

    try {
      const response = a{
        setIsTyping(false);
        return; // Request was cancelled or outdated
      }
        message: userMessageContent,
        conversation_id: isNewConversation ? undefined : currentConversationId!,
        conversation_title: isNewConversation ? `Chat ${new Date().toLocaleString()}` : undefined,
      });

      // Get request info
      const requestInfo = pendingRequestsRef.current.get(tempId);
      if (!requestInfo) return; // Request was cancelled or outdated

      const { conversationKey: targetConvKey, userTempId: targetUserTempId } = requestInfo;
      pendingRequestsRef.current.delete(tempId);

      // Get the target conversation state (might be different from current if user switched)
      const targetState = getConversationState(targetConvKey);

      // Remove pending messages and add real messages
      const messagesWithoutPending = targetState.messages.filter(m => m.tempId !== targetUserTempId);

      // Create real messages
      const realUserMessage: Message = {
        id: response.message_id - 1, // Assuming user message ID is one less (adjust as needed)
        conversation_id: response.conversation_id,
        content: userMessageContent,
        sender: 'user',
        is_high_risk: false,
        is_mental_health_related: true,
        created_at: now,
      };

      const botMessage: Message = {
        id: response.message_id,
        conversation_id: response.conversation_id,
        content: response.answer,
        sender: 'bot',
        is_high_risk: response.is_high_risk,
        is_mental_health_related: response.is_mental_health_related,
        created_at: new Date().toISOString(),
      };

      // Update server messages
      const newServerMessages = [...targetState.serverMessages, realUserMessage, botMessage];

      // Merge with any remaining pending messages
      const finalMessages = mergeMessages(newServerMessages, messagesWithoutPending);

      updateConversationState(targetConvKey, {
        messages: finalMessages,
        serverMessages: newServerMessages,
        pendingCount: Math.max(0, targetState.pendingCount - 1),
      });

      // Reload conversations list
      await loadConversations();

      // Handle new conversation creation
      if (isNewConversation) {
        // Xóa placeholder conversation
        setConversations(prev => prev.filter(c => c.id >= 0));
        
        // Move state to the actual conversation ID
        const realConvKey = getConversationKey(response.conversation_id);
        conversationStatesRef.current.set(realConvKey, {
          messages: finalMessages,
          serverMessages: newServerMessages,
          inputDraft: '',
          pendingCount: 0,
        });
        
        // Clean up old states
        conversationStatesRef.current.delete(targetConvKey);
        conversationStatesRef.current.delete('new');
  
      // Hide typing indicator
      setIsTyping(false);
    } catch (error) {
      console.error('Error sending message:', error);
      setIsTyping(false
        setCurrentConversationId(response.conversation_id);
      } else {
        forceUpdate();
      }
    } catch (error) {
      console.error('Error sending message:', error);

      // Remove from pending requests
      pendingRequestsRef.current.delete(tempId);

      // Get current state
      const currentState = getConversationState(convKey);

      // Remove pending message and add error message
      const messagesWithoutPending = currentState.messages.filter(m => m.tempId !== userTempId);

      const errorMessage: Message = {
        id: Date.now(),
        conversation_id: currentConversationId ?? 0,
        content: 'Xin lỗi, đã xảy ra lỗi. Vui lòng thử lại.',
        sender: 'bot',
        is_high_risk: false,
        is_mental_health_related: false,
        created_at: new Date().toISOString(),
      };

      updateConversationState(convKey, {
        messages: [...messagesWithoutPending, errorMessage],
        pendingCount: Math.max(0, currentState.pendingCount - 1),
      });

    // Don't force update on every keystroke for better performance
  };

  const handleLogout = () => {
    logout();
  };

  // Get current conversation state for rendering
  const convKey = getConversationKey(currentConversationId);
  const currentState = getConversationState(convKey);
  const currentConversation = conversations.find(c => c.id === currentConversationId);

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <div className="relative">
        <ChatSidebar
          isCollapsed={isSidebarCollapsed}
          onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
          activeChat={currentConversationId}
          conversations={conversations}
          onChatSelect={handleSelectConversation}
          onNewChat={handleNewConversation}
          onDeleteChat={handleDeleteConversation}
          onRenameChat={handleRenameConversation}
          onLogout={handleLogout}
          userEmail={user?.email}
        />
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col bg-background">
        {/* Top Bar */}
        <div className="h-16 border-b border-border bg-card/50 backdrop-blur-sm px-6 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
              className="lg:hidden w-9 h-9 rounded-lg hover:bg-muted flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors"
            >
              <Menu className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-lg font-semibold text-foreground">
                {currentConversation?.title || 'MenChat'}
              </h1>
              <div className="text-xs text-muted-foreground">
                Tư vấn tâm lý • {currentConversationId ? 'Đang trò chuyện' : 'Bắt đầu mới'}
              </div>
            </div>
          </div>
        </div>

        {/* Chat Area */}
        <div className="flex-1 overflow-y-auto">
          {currentState.messages.length === 0 ? (
            <EmptyState onNewChat={handleNewConversation} />
          ) : (
            <div className="max-w-4xl mx-auto px-6 py-8">
              {currentState.messages.map((message) => (
                <ChatMessage key={message.tempId || message.id} message={message} />
              ))}
              
              {/* Typing Indicator */}
              {isTyping && (
                <div className="flex gap-4 mb-6">
                  <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-slate-100 to-slate-50 border border-border flex items-center justify-center flex-shrink-0">
                    <Bot className="w-5 h-5 text-muted-foreground" />
                  </div>
                  <div className="flex-1 max-w-[75%]">
                    <div className="rounded-2xl rounded-tl-md px-5 py-4 bg-white border border-border shadow-sm">
                      <div className="flex gap-1.5">
                        <div className="w-2 h-2 rounded-full bg-primary/60 animate-bounce" style={{ animationDelay: '0ms' }}></div>
                        <div className="w-2 h-2 rounded-full bg-primary/60 animate-bounce" style={{ animationDelay: '150ms' }}></div>
                        <div className="w-2 h-2 rounded-full bg-primary/60 animate-bounce" style={{ animationDelay: '300ms' }}></div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
              
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Composer */}
        <ChatComposer 
          onSendMessage={handleSendMessage}
          disabled={isTyping}
          inputValue={currentState.inputDraft}
          onInputChange={handleInputChan
        <ChatInterface
          messages={currentState.messages}
          inputValue={currentState.inputDraft}
          isLoading={currentState.pendingCount > 0}
          currentConversationTitle={currentConversation?.title}
          onInputChange={handleInputChange}
          onSendMessage={handleSendMessage}
        />
      </div>
    </div>
  );
};

export default Home;
