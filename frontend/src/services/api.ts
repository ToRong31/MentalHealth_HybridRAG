/**
 * API Client for Mental Health Chatbot
 * Handles all HTTP requests to the backend
 */

import type {
    AuthResponse,
    RegisterRequest,
    LoginRequest,
    Conversation,
    ConversationWithMessages,
    ChatRequest,
    ChatResponse,
    User
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Get authentication token from localStorage
 */
function getAuthToken(): string | null {
    return localStorage.getItem('auth_token');
}

/**
 * Set authentication token in localStorage
 */
function setAuthToken(token: string): void {
    localStorage.setItem('auth_token', token);
}

/**
 * Remove authentication token from localStorage
 */
function clearAuthToken(): void {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user');
}

/**
 * Make authenticated API request
 */
async function apiRequest<T>(
    endpoint: string,
    options: RequestInit = {}
): Promise<T> {
    const token = getAuthToken();
    console.log('[API] Request to:', endpoint);
    console.log('[API] Token exists:', !!token);
    console.log('[API] Token value:', token?.substring(0, 20) + '...');

    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
    };

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
        console.log('[API] Authorization header set');
    } else {
        console.warn('[API] No token found in localStorage');
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...options,
        headers: {
            ...headers,
            ...(options.headers as Record<string, string>),
        },
    });

    if (response.status === 401) {
        // Token expired or invalid
        clearAuthToken();
        window.location.href = '/';
        throw new Error('Unauthorized');
    }

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(error.detail || 'Request failed');
    }

    // Handle 204 No Content
    if (response.status === 204) {
        return null as T;
    }

    return response.json();
}

// ================================
// Authentication API
// ================================

export async function register(data: RegisterRequest): Promise<AuthResponse> {
    const response = await apiRequest<AuthResponse>('/api/v1/auth/register', {
        method: 'POST',
        body: JSON.stringify(data),
    });

    setAuthToken(response.token.access_token);
    localStorage.setItem('user', JSON.stringify(response.user));

    return response;
}

export async function login(data: LoginRequest): Promise<AuthResponse> {
    const response = await apiRequest<AuthResponse>('/api/v1/auth/login', {
        method: 'POST',
        body: JSON.stringify(data),
    });

    console.log('[AUTH] Login response:', response);
    console.log('[AUTH] Token:', response.token.access_token.substring(0, 20) + '...');

    setAuthToken(response.token.access_token);
    localStorage.setItem('user', JSON.stringify(response.user));

    console.log('[AUTH] Token saved to localStorage');
    console.log('[AUTH] Stored token:', localStorage.getItem('auth_token')?.substring(0, 20) + '...');

    return response;
}

export async function getCurrentUser(): Promise<User> {
    return apiRequest<User>('/api/v1/auth/me');
}

export function logout(): void {
    clearAuthToken();
}

export function isAuthenticated(): boolean {
    return getAuthToken() !== null;
}

export function getStoredUser(): User | null {
    const userJson = localStorage.getItem('user');
    if (!userJson) return null;
    try {
        return JSON.parse(userJson);
    } catch {
        return null;
    }
}

// ================================
// Conversation API
// ================================

export async function getConversations(): Promise<Conversation[]> {
    return apiRequest<Conversation[]>('/api/v1/conversations');
}

export async function createConversation(title: string): Promise<Conversation> {
    return apiRequest<Conversation>('/api/v1/conversations', {
        method: 'POST',
        body: JSON.stringify({ title }),
    });
}

export async function getConversation(id: number): Promise<ConversationWithMessages> {
    return apiRequest<ConversationWithMessages>(`/api/v1/conversations/${id}`);
}

export async function deleteConversation(id: number): Promise<void> {
    return apiRequest<void>(`/api/v1/conversations/${id}`, {
        method: 'DELETE',
    });
}

// ================================
// Chat API
// ================================

export async function sendMessage(data: ChatRequest): Promise<ChatResponse> {
    return apiRequest<ChatResponse>('/api/v1/chat', {
        method: 'POST',
        body: JSON.stringify(data),
    });
}
