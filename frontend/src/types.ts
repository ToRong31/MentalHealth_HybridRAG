/**
 * TypeScript interfaces for the Mental Health Chatbot
 */

export interface User {
    id: number;
    username: string;
    email: string;
    created_at: string;
}

export interface Conversation {
    id: number;
    user_id: number;
    title: string;
    created_at: string;
    updated_at: string;
}

export interface Message {
    id: number;
    conversation_id: number;
    content: string;
    sender: 'user' | 'bot';
    is_high_risk: boolean;
    is_mental_health_related: boolean;
    created_at: string;
}

export interface ConversationWithMessages extends Conversation {
    messages: Message[];
}

export interface AuthResponse {
    user: User;
    token: {
        access_token: string;
        token_type: string;
    };
}

export interface ChatRequest {
    message: string;
    conversation_id?: number;
    conversation_title?: string;
}

export interface ChatResponse {
    answer: string;
    is_mental_health_related: boolean;
    is_high_risk: boolean;
    conversation_id: number;
    message_id: number;
}

export interface RegisterRequest {
    username: string;
    email: string;
    password: string;
}

export interface LoginRequest {
    email: string;
    password: string;
}
