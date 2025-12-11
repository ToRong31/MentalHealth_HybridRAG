/**
 * API Client for Mental Health Chatbot
 * Handles all HTTP requests to the backend with automatic token refresh
 */

import axios, {
    AxiosError,
    type AxiosInstance,
    type InternalAxiosRequestConfig,
    type AxiosResponse,
} from 'axios';
import tokenService from './tokenService';
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

const API_BASE_URL = ((import.meta as { env?: { VITE_API_URL?: string } }).env?.VITE_API_URL) || 'http://localhost:8000';

// Create axios instance
const api: AxiosInstance = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
    withCredentials: true, // Important for cookies (refresh token)
});

// Request interceptor: Add access token to requests
api.interceptors.request.use(
    async (config: InternalAxiosRequestConfig) => {
        const token = tokenService.getAccessToken();

        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }

        return config;
    },
    (error: AxiosError) => Promise.reject(error)
);

// Response interceptor: Handle 401 errors with token refresh retry
api.interceptors.response.use(
    (response: AxiosResponse) => response,
    async (error: AxiosError) => {
        const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

        // If 401 and haven't retried yet, try refreshing token
        if (error.response?.status === 401 && !originalRequest._retry) {
            originalRequest._retry = true;

            try {
                console.log('[API] 401 error, attempting token refresh...');
                const newToken = await tokenService.refreshAccessToken();

                // Retry original request with new token
                originalRequest.headers.Authorization = `Bearer ${newToken}`;
                return api(originalRequest);
            } catch (refreshError) {
                // Refresh failed, clear token and let user re-login
                console.error('[API] Token refresh failed:', refreshError);
                tokenService.clearAccessToken();
                return Promise.reject(refreshError);
            }
        }

        return Promise.reject(error);
    }
);

/**
 * Remove authentication data
 */
function clearAuthData(): void {
    tokenService.clearAccessToken();
    localStorage.removeItem('user');
}

// ================================
// Authentication API
// ================================

export async function register(data: RegisterRequest): Promise<AuthResponse> {
    const response = await api.post<AuthResponse>('/api/v1/auth/register', data);

    // Store access token and user
    tokenService.setAccessToken(response.data.token.access_token, response.data.token.expires_in);
    localStorage.setItem('user', JSON.stringify(response.data.user));

    return response.data;
}

export async function login(data: LoginRequest): Promise<AuthResponse> {
    const response = await api.post<AuthResponse>('/api/v1/auth/login', data);

    console.log('[AUTH] Login response:', response.data);

    // Store access token (refresh token is in httpOnly cookie)
    tokenService.setAccessToken(response.data.token.access_token, response.data.token.expires_in);
    localStorage.setItem('user', JSON.stringify(response.data.user));

    console.log('[AUTH] Access token stored in memory');

    return response.data;
}

export async function getCurrentUser(): Promise<User> {
    const response = await api.get<User>('/api/v1/auth/me');
    return response.data;
}

export async function logout(): Promise<void> {
    try {
        await api.post('/api/v1/auth/logout');
    } catch (error) {
        console.error('[AUTH] Logout request failed:', error);
    } finally {
        clearAuthData();
    }
}

export function isAuthenticated(): boolean {
    return tokenService.getAccessToken() !== null;
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
    const response = await api.get<Conversation[]>('/api/v1/conversations');
    return response.data;
}

export async function createConversation(title: string): Promise<Conversation> {
    const response = await api.post<Conversation>('/api/v1/conversations', { title });
    return response.data;
}

export async function getConversation(id: number): Promise<ConversationWithMessages> {
    const response = await api.get<ConversationWithMessages>(`/api/v1/conversations/${id}`);
    return response.data;
}

export async function deleteConversation(id: number): Promise<void> {
    await api.delete(`/api/v1/conversations/${id}`);
}

// ================================
// Chat API
// ================================

export async function sendMessage(data: ChatRequest): Promise<ChatResponse> {
    const response = await api.post<ChatResponse>('/api/v1/chat', data);
    return response.data;
}

export default api;

