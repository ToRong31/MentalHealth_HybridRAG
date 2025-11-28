import React, { useState, useEffect } from 'react';
import Sidebar from '../components/Sidebar';
import Header from '../components/Header';
import ChatInterface from '../components/ChatInterface';
import {
    getConversations,
    getConversation,
    createConversation,
    deleteConversation,
    sendMessage,
} from '../services/api';
import type { Conversation, Message, ConversationWithMessages } from '../types';

const Home: React.FC = () => {
    // Conversation state
    const [conversations, setConversations] = useState<Conversation[]>([]);
    const [currentConversation, setCurrentConversation] = useState<ConversationWithMessages | null>(null);
    const [messages, setMessages] = useState<Message[]>([]);

    // Chat state
    const [inputValue, setInputValue] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    // UI state
    const [sidebarOpen, setSidebarOpen] = useState(true);

    // Load conversations on mount
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

    const handleNewConversation = async () => {
        try {
            const title = `New Chat ${new Date().toLocaleString()}`;
            const conversation = await createConversation(title);
            setConversations([conversation, ...conversations]);
            setCurrentConversation({ ...conversation, messages: [] });
            setMessages([]);
        } catch (error) {
            console.error('Error creating conversation:', error);
        }
    };

    const handleSelectConversation = async (conversationId: number) => {
        try {
            const conversation = await getConversation(conversationId);
            setCurrentConversation(conversation);
            setMessages(conversation.messages);
        } catch (error) {
            console.error('Error loading conversation:', error);
        }
    };

    const handleDeleteConversation = async (conversationId: number) => {
        if (!confirm('Are you sure you want to delete this conversation?')) return;

        try {
            await deleteConversation(conversationId);
            setConversations(conversations.filter((c) => c.id !== conversationId));
            if (currentConversation?.id === conversationId) {
                setCurrentConversation(null);
                setMessages([]);
            }
        } catch (error) {
            console.error('Error deleting conversation:', error);
        }
    };

    const handleSendMessage = async () => {
        if (!inputValue.trim() || isLoading) return;

        const userMessageContent = inputValue;
        setInputValue('');
        setIsLoading(true);

        // Optimistically add user message to UI
        const tempUserMessage: Message = {
            id: Date.now(),
            conversation_id: currentConversation?.id || 0,
            content: userMessageContent,
            sender: 'user',
            is_high_risk: false,
            is_mental_health_related: true,
            created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, tempUserMessage]);

        try {
            const response = await sendMessage({
                message: userMessageContent,
                conversation_id: currentConversation?.id,
                conversation_title: currentConversation
                    ? undefined
                    : `Chat ${new Date().toLocaleString()}`,
            });

            // If this was a new conversation, update state
            if (!currentConversation) {
                await loadConversations();
                const newConv = await getConversation(response.conversation_id);
                setCurrentConversation(newConv);
                setMessages(newConv.messages);
            } else {
                // Add bot message
                const botMessage: Message = {
                    id: response.message_id,
                    conversation_id: response.conversation_id,
                    content: response.answer,
                    sender: 'bot',
                    is_high_risk: response.is_high_risk,
                    is_mental_health_related: response.is_mental_health_related,
                    created_at: new Date().toISOString(),
                };
                setMessages((prev) => [...prev, botMessage]);

                // Update conversation list
                await loadConversations();
            }
        } catch (error) {
            console.error('Error sending message:', error);
            const errorMessage: Message = {
                id: Date.now() + 1,
                conversation_id: currentConversation?.id || 0,
                content: 'Sorry, I encountered an error. Please try again.',
                sender: 'bot',
                is_high_risk: false,
                is_mental_health_related: false,
                created_at: new Date().toISOString(),
            };
            setMessages((prev) => [...prev, errorMessage]);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="app-container">
            <Sidebar
                conversations={conversations}
                currentConversationId={currentConversation?.id}
                isOpen={sidebarOpen}
                onToggle={() => setSidebarOpen(!sidebarOpen)}
                onNewConversation={handleNewConversation}
                onSelectConversation={handleSelectConversation}
                onDeleteConversation={handleDeleteConversation}
            />

            <div className="chat-container">
                <Header
                    title={currentConversation?.title || 'Select or create a conversation'}
                    subtitle="Your confidential companion for mental wellness"
                />

                <ChatInterface
                    messages={messages}
                    inputValue={inputValue}
                    isLoading={isLoading}
                    currentConversationTitle={currentConversation?.title}
                    onInputChange={setInputValue}
                    onSendMessage={handleSendMessage}
                />
            </div>
        </div>
    );
};

export default Home;
