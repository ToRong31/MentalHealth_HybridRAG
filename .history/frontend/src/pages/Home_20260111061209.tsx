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

interface ConversationState {
  messages: Message[];
  inputDraft: string;
  pendingCount: number;
  serverMessages: Message[];
}

const Home: React.FC = () => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<number | null>(null);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { user, logout } = useAuth();
  
  const [, setRenderTrigger] = useState(0);
  const forceUpdate = useCallback(() => setRenderTrigger(prev => prev + 1), []);

  const conversationStatesRef = useRef<Map<string, ConversationState>>(new Map());
  const pendingRequestsRef = useRef<Map<string, { conversationKey: string; userTempId: string }>>(new Map());

  const getConversationKey = (convId: number | null): string => {
    return convId === null ? 'new' : convId.toString();
  };

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

  const updateConversationState = useCallback((convKey: string, updates: Partial<ConversationState>) => {
    const current = getConversationState(convKey);
    conversationStatesRef.current.set(convKey, { ...current, ...updates });
  }, [getConversationState]);

  const mergeMessages = useCallback((serverMessages: Message[], pendingMessages: Message[]): Message[] => {
    const serverMap = new Map(serverMessages.map(m => [m.id, m]));
    const merged: Message[] = [...serverMessages];

    pendingMessages.forEach(pm => {
      if (pm.isPending && !serverMap.has(pm.id)) {
        merged.push(pm);
      }
    });

    return merged.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
  }, []);

  useEffect(() => {
    loadConversations();
  }, []);

  const convKey = getConversationKey(currentConversationId);
  const currentState = getConversationState(convKey);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [currentState.messages]);

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
  };

  const handleSelectConversation = async (conversationId: number) => {
    try {
      const convKey = getConversationKey(conversationId);
      const state = getConversationState(convKey);

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

      const convKey = getConversationKey(conversationId);
      conversationStatesRef.current.delete(convKey);

      if (currentConversationId === conversationId) {
        setCurrentConversationId(null);
      }
    } catch (error) {
      console.error('Error deleting conversation:', error);
    }
  };

  const handleSendMessage = async (message?: string) => {
    const convKey = getConversationKey(currentConversationId);
    const state = getConversationState(convKey);
    const userMessageContent = (message || state.inputDraft).trim();

    if (!userMessageContent) return;

    setIsTyping(true);

    const tempId = `temp-${Date.now()}-${Math.random()}`;
    const userTempId = `user-${tempId}`;
    const now = new Date().toISOString();
    
    const isNewConversation = currentConversationId === null;
    let workingConversationId = currentConversationId;
    
    if (isNewConversation) {
      const placeholderConv: Conversation = {
        id: -Date.now(),
        user_id: 0,
        title: `Chat ${new Date().toLocaleTimeString()}`,
        created_at: now,
        updated_at: now,
      };
      setConversations(prev => [placeholderConv, ...prev]);
      workingConversationId = placeholderConv.id;
      setCurrentConversationId(workingConversationId);
    }

    const pendingUserMessage: Message = {
      id: Date.now(),
      conversation_id: workingConversationId ?? 0,
      content: userMessageContent,
      sender: 'user',
      is_high_risk: false,
      is_mental_health_related: true,
      created_at: now,
      isPending: true,
      tempId: userTempId,
    };

    const workingConvKey = getConversationKey(workingConversationId);
    const workingState = getConversationState(workingConvKey);
    const updatedMessages = [...workingState.messages, pendingUserMessage];
    updateConversationState(workingConvKey, {
      messages: updatedMessages,
      inputDraft: '',
      pendingCount: workingState.pendingCount + 1,
    });

    forceUpdate();

    pendingRequestsRef.current.set(tempId, { conversationKey: workingConvKey, userTempId });

    try {
      const response = await sendMessage({
        message: userMessageContent,
        conversation_id: isNewConversation ? undefined : currentConversationId!,
        conversation_title: isNewConversation ? `Chat ${new Date().toLocaleString()}` : undefined,
      });

      const requestInfo = pendingRequestsRef.current.get(tempId);
      if (!requestInfo) {
        setIsTyping(false);
        return;
      }

      const { conversationKey: targetConvKey, userTempId: targetUserTempId } = requestInfo;
      pendingRequestsRef.current.delete(tempId);

      const targetState = getConversationState(targetConvKey);

      const messagesWithoutPending = targetState.messages.filter(m => m.tempId !== targetUserTempId);

      const realUserMessage: Message = {
        id: response.message_id - 1,
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

      const newServerMessages = [...targetState.serverMessages, realUserMessage, botMessage];
      const finalMessages = mergeMessages(newServerMessages, messagesWithoutPending);

      updateConversationState(targetConvKey, {
        messages: finalMessages,
        serverMessages: newServerMessages,
        pendingCount: Math.max(0, targetState.pendingCount - 1),
      });

      await loadConversations();

      if (isNewConversation) {
        setConversations(prev => prev.filter(c => c.id >= 0));
        
        const realConvKey = getConversationKey(response.conversation_id);
        conversationStatesRef.current.set(realConvKey, {
          messages: finalMessages,
          serverMessages: newServerMessages,
          inputDraft: '',
          pendingCount: 0,
        });
        
        conversationStatesRef.current.delete(targetConvKey);
        conversationStatesRef.current.delete('new');

        setCurrentConversationId(response.conversation_id);
      } else {
        forceUpdate();
      }
      
      setIsTyping(false);
    } catch (error) {
      console.error('Error sending message:', error);
      setIsTyping(false);

      pendingRequestsRef.current.delete(tempId);

      const currentState = getConversationState(convKey);

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

      forceUpdate();
    }
  };

  const handleInputChange = (value: string) => {
    const convKey = getConversationKey(currentConversationId);
    updateConversationState(convKey, { inputDraft: value });
  };

  const handleLogout = () => {
    logout();
  };

  const currentConversation = conversations.find(c => c.id === currentConversationId);

  return (
    <div className="flex h-screen overflow-hidden">
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

      <div className="flex-1 flex flex-col bg-background">
        <div className="h-16 border-b border-border bg-card/50 backdrop-blur-sm px-6 flex items-center justify-between shrink-0">
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

        <div className="flex-1 overflow-y-auto">
          {currentState.messages.length === 0 ? (
            <EmptyState onNewChat={handleNewConversation} />
          ) : (
            <div className="max-w-4xl mx-auto px-6 py-8">
              {currentState.messages.map((message) => (
                <ChatMessage key={message.tempId || message.id} message={message} />
              ))}
              
              {isTyping && (
                <div className="flex gap-4 mb-6">
                  <div className="w-9 h-9 rounded-xl bg-linear-to-br from-slate-100 to-slate-50 border border-border flex items-center justify-center shrink-0">
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

        <ChatComposer 
          onSendMessage={handleSendMessage}
          disabled={isTyping}
          inputValue={currentState.inputDraft}
          onInputChange={handleInputChange}
        />
      </div>
    </div>
  );
};

export default Home;
