import React, { useState, useEffect, useRef } from 'react';
import Sidebar from '../components/Sidebar';
import Header from '../components/Header';
import ChatInterface from '../components/ChatInterface';
import {
  getConversations,
  getConversation,
  updateConversation,
  deleteConversation,
  sendMessage,
} from '../services/api';
import type { Conversation, Message, ConversationWithMessages } from '../types';

const Home: React.FC = () => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversation, setCurrentConversation] = useState<ConversationWithMessages | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');

  // ✅ Loading theo conversation (không bị “lây” sang chat khác)
  const [loadingConversationId, setLoadingConversationId] = useState<number | null>(null);

  const [sidebarOpen, setSidebarOpen] = useState(true);

  // ✅ Token để biết response này thuộc “lần gửi” nào (tránh race condition)
  const requestSeqRef = useRef(0);

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
    setCurrentConversation(null);
    setMessages([]);
    setInputValue('');
    // ✅ chuyển chat mới thì không còn loading chat cũ
    setLoadingConversationId(null);
  };

  const handleSelectConversation = async (conversationId: number) => {
    try {
      // ✅ chuyển chat khác thì không còn hiện “đang suy nghĩ” của chat trước
      setLoadingConversationId(null);

      const conversation = await getConversation(conversationId);
      setCurrentConversation(conversation);
      setMessages(conversation.messages);
      setInputValue('');
    } catch (error) {
      console.error('Error loading conversation:', error);
    }
  };

  const handleRenameConversation = async (conversationId: number, newTitle: string) => {
    try {
      const updatedConv = await updateConversation(conversationId, newTitle);
      setConversations(conversations.map((c) => (c.id === conversationId ? updatedConv : c)));

      if (currentConversation?.id === conversationId) {
        setCurrentConversation({
          ...currentConversation,
          title: updatedConv.title,
          updated_at: updatedConv.updated_at,
        });
      }
    } catch (error) {
      console.error('Error renaming conversation:', error);
    }
  };

  const handleDeleteConversation = async (conversationId: number) => {
    if (!confirm('Bạn có chắc chắn muốn xóa đoạn chat này?')) return;

    try {
      await deleteConversation(conversationId);
      setConversations(conversations.filter((c) => c.id !== conversationId));

      if (currentConversation?.id === conversationId) {
        setCurrentConversation(null);
        setMessages([]);
        setInputValue('');
        setLoadingConversationId(null);
      } else if (loadingConversationId === conversationId) {
        setLoadingConversationId(null);
      }
    } catch (error) {
      console.error('Error deleting conversation:', error);
    }
  };

  const handleSendMessage = async () => {
    const userMessageContent = inputValue.trim();
    const currentId = currentConversation?.id ?? null;

    // ✅ chặn gửi khi đang loading đúng conversation hiện tại
    if (!userMessageContent) return;
    if (loadingConversationId !== null && loadingConversationId === currentId) return;

    // tạo token cho lần gửi này
    const myRequestSeq = ++requestSeqRef.current;

    const tempUserMessage: Message = {
      id: -Date.now(),
      conversation_id: currentId ?? 0,
      content: userMessageContent,
      sender: 'user',
      is_high_risk: false,
      is_mental_health_related: true,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, tempUserMessage]);
    setInputValue('');

    // ✅ set loading cho đúng conversation đang mở (null nếu là new conversation)
    setLoadingConversationId(currentId);

    try {
      const response = await sendMessage({
        message: userMessageContent,
        conversation_id: currentId ?? undefined,
        conversation_title: currentConversation ? undefined : `Chat ${new Date().toLocaleString()}`,
      });

      // ✅ Nếu trong lúc chờ user đã gửi lần khác -> bỏ qua response cũ
      if (myRequestSeq !== requestSeqRef.current) return;

      // ✅ Nếu user đang đứng ở chat khác khi response về -> KHÔNG append nhầm
      const stillViewingSameConversation =
        (currentConversation?.id ?? null) === (response.conversation_id ?? null);

      const botMessage: Message = {
        id: response.message_id,
        conversation_id: response.conversation_id,
        content: response.answer,
        sender: 'bot',
        is_high_risk: response.is_high_risk,
        is_mental_health_related: response.is_mental_health_related,
        created_at: new Date().toISOString(),
      };

      if (stillViewingSameConversation) {
        setMessages((prev) => [...prev, botMessage]);
      }

      // cập nhật list
      await loadConversations();

      // nếu là new conversation và user vẫn đang ở “new conversation view” (currentConversation null)
      if (!currentConversation && response.conversation_id) {
        // chỉ auto-switch nếu user vẫn đang ở màn hình “new”
        const newConv = await getConversation(response.conversation_id);
        setCurrentConversation(newConv);
        setMessages(newConv.messages);
      }
    } catch (error) {
      console.error('Error sending message:', error);

      // ✅ chỉ show lỗi nếu user vẫn đang ở đúng chat lúc gửi
      const stillSame = (currentConversation?.id ?? null) === currentId;
      if (stillSame) {
        const errorMessage: Message = {
          id: Date.now(),
          conversation_id: currentId ?? 0,
          content: 'Xin lỗi, đã xảy ra lỗi. Vui lòng thử lại.',
          sender: 'bot',
          is_high_risk: false,
          is_mental_health_related: false,
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, errorMessage]);
      }
    } finally {
      // ✅ chỉ tắt loading nếu đây là request mới nhất
      if (myRequestSeq === requestSeqRef.current) {
        setLoadingConversationId(null);
      }
    }
  };

  const currentConversationId = currentConversation?.id ?? null;
  const isLoading = loadingConversationId !== null && loadingConversationId === currentConversationId;

  return (
    <div className="app-container">
      <Sidebar
        conversations={conversations}
        currentConversationId={currentConversation?.id}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        onNewConversation={handleNewConversation}
        onSelectConversation={handleSelectConversation}
        onRenameConversation={handleRenameConversation}
        onDeleteConversation={handleDeleteConversation}
      />

      <div className="chat-container">
        <Header
          title={currentConversation?.title || 'Select or create a conversation'}
          subtitle="MenChat • Confidential support, always on"
        />

        <ChatInterface
          messages={messages}
          inputValue={inputValue}
          isLoading={isLoading} // ✅ giờ chỉ loading đúng chat
          currentConversationTitle={currentConversation?.title}
          onInputChange={setInputValue}
          onSendMessage={handleSendMessage}
        />
      </div>
    </div>
  );
};

export default Home;
