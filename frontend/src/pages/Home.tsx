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

// State for each conversation
interface ConversationState {
    messages: Message[];
    inputValue: string;
    isLoading: boolean;
}

const Home: React.FC = () => {
    // Conversation state
    const [conversations, setConversations] = useState<Conversation[]>([]);
    const [currentConversation, setCurrentConversation] = useState<ConversationWithMessages | null>(null);

    // Per-conversation state management
    const [conversationStates, setConversationStates] = useState<Map<number | 'new', ConversationState>>(new Map());

    // UI state
    const [sidebarOpen, setSidebarOpen] = useState(true);

    // Load conversations on mount
    useEffect(() => {
        loadConversations();
    }, []);

    // Get current conversation state
    const getCurrentState = (): ConversationState => {
        const key = currentConversation?.id ?? 'new';
        return conversationStates.get(key) ?? {
            messages: [],
            inputValue: '',
            isLoading: false,
        };
    };

    // Update current conversation state
    const updateCurrentState = (updates: Partial<ConversationState>) => {
        const key = currentConversation?.id ?? 'new';
        const currentState = getCurrentState();
        const newState = { ...currentState, ...updates };
        setConversationStates(new Map(conversationStates.set(key, newState)));
    };

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

            // Initialize state for new conversation
            const newState: ConversationState = {
                messages: [],
                inputValue: '',
                isLoading: false,
            };
            setConversationStates(new Map(conversationStates.set(conversation.id, newState)));
        } catch (error) {
            console.error('Error creating conversation:', error);
        }
    };

    const handleSelectConversation = async (conversationId: number) => {
        try {
            const conversation = await getConversation(conversationId);
            setCurrentConversation(conversation);

            // Initialize state if not exists
            if (!conversationStates.has(conversationId)) {
                const newState: ConversationState = {
                    messages: conversation.messages,
                    inputValue: '',
                    isLoading: false,
                };
                setConversationStates(new Map(conversationStates.set(conversationId, newState)));
            } else {
                // Update messages from server (in case they changed)
                updateCurrentState({ messages: conversation.messages });
            }
        } catch (error) {
            console.error('Error loading conversation:', error);
        }
    };

    const handleDeleteConversation = async (conversationId: number) => {
        if (!confirm('Are you sure you want to delete this conversation?')) return;

        try {
            await deleteConversation(conversationId);
            setConversations(conversations.filter((c) => c.id !== conversationId));

            // Remove state for deleted conversation
            const newStates = new Map(conversationStates);
            newStates.delete(conversationId);
            setConversationStates(newStates);

            if (currentConversation?.id === conversationId) {
                setCurrentConversation(null);
            }
        } catch (error) {
            console.error('Error deleting conversation:', error);
        }
    };

    const handleSendMessage = async () => {
        const currentState = getCurrentState();
        if (!currentState.inputValue.trim() || currentState.isLoading) return;

        const userMessageContent = currentState.inputValue;
        const conversationIdForMessage = currentConversation?.id;

        // Clear input and set loading for THIS conversation
        updateCurrentState({
            inputValue: '',
            isLoading: true
        });

        // Optimistically add user message to UI for THIS conversation
        const tempUserMessage: Message = {
            id: Date.now(),
            conversation_id: conversationIdForMessage || 0,
            content: userMessageContent,
            sender: 'user',
            is_high_risk: false,
            is_mental_health_related: true,
            created_at: new Date().toISOString(),
        };

        updateCurrentState({
            messages: [...currentState.messages, tempUserMessage]
        });

        try {
            const response = await sendMessage({
                message: userMessageContent,
                conversation_id: conversationIdForMessage,
                conversation_title: currentConversation
                    ? undefined
                    : `Chat ${new Date().toLocaleString()}`,
            });

            // If this was a new conversation, update state
            if (!conversationIdForMessage) {
                // Load new conversation details
                const newConv = await getConversation(response.conversation_id);
                setCurrentConversation(newConv);

                // Move state from 'new' to actual conversation ID
                const newKey = response.conversation_id;
                const newState: ConversationState = {
                    messages: newConv.messages,
                    inputValue: '',
                    isLoading: false,
                };
                const newStates = new Map(conversationStates);
                newStates.delete('new');
                newStates.set(newKey, newState);
                setConversationStates(newStates);

                // Refresh list in background
                loadConversations();
            } else {
                // Add bot message to THIS conversation
                const botMessage: Message = {
                    id: response.message_id,
                    conversation_id: response.conversation_id,
                    content: response.answer,
                    sender: 'bot',
                    is_high_risk: response.is_high_risk,
                    is_mental_health_related: response.is_mental_health_related,
                    created_at: new Date().toISOString(),
                };

                // Get the latest state for this conversation
                const key = conversationIdForMessage;
                const latestState = conversationStates.get(key) ?? currentState;
                const updatedMessages = [...latestState.messages, botMessage];

                const newStates = new Map(conversationStates);
                newStates.set(key, {
                    ...latestState,
                    messages: updatedMessages,
                    isLoading: false,
                });
                setConversationStates(newStates);

                // Update conversation list in background
                loadConversations();
            }
        } catch (error) {
            console.error('Error sending message:', error);

            const errorMessage: Message = {
                id: Date.now() + 1,
                conversation_id: conversationIdForMessage || 0,
                content: 'Sorry, I encountered an error. Please try again.',
                sender: 'bot',
                is_high_risk: false,
                is_mental_health_related: false,
                created_at: new Date().toISOString(),
            };

            // Add error message to THIS conversation
            const key = conversationIdForMessage ?? 'new';
            const latestState = conversationStates.get(key) ?? currentState;
            const updatedMessages = [...latestState.messages, errorMessage];

            const newStates = new Map(conversationStates);
            newStates.set(key, {
                ...latestState,
                messages: updatedMessages,
                isLoading: false,
            });
            setConversationStates(newStates);
        }
    };


    const currentState = getCurrentState();

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
                    messages={currentState.messages}
                    inputValue={currentState.inputValue}
                    isLoading={currentState.isLoading}
                    currentConversationTitle={currentConversation?.title}
                    onInputChange={(value) => updateCurrentState({ inputValue: value })}
                    onSendMessage={handleSendMessage}
                />
            </div>
        </div>
    );
};

export default Home;
