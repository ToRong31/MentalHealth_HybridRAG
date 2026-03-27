import React, { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { register, login, logout as apiLogout, getStoredUser } from '../services/api';
import tokenService from '../services/tokenService';
import type { User } from '../types';

interface AuthContextType {
    user: User | null;
    login: (email: string, password: string) => Promise<void>;
    register: (username: string, email: string, password: string) => Promise<void>;
    logout: () => void;
    isLoading: boolean;
    error: string;
    clearError: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Mock test user - for frontend testing without backend
const TEST_USER: User = {
    id: 999,
    username: 'testuser',
    email: 'test@test.com',
    created_at: new Date().toISOString()
};

const TEST_CREDENTIALS = {
    email: 'test@test.com',
    password: 'test123'
};

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<User | null>(getStoredUser());
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');

    // ✅ Restore session on mount: if user exists but token is invalid, try refresh
    useEffect(() => {
        const restoreSession = async () => {
            const storedUser = getStoredUser();
            const token = tokenService.getAccessToken();

            // If user is stored but no token (shouldn't happen now with localStorage), or token expired
            if (storedUser && (!token || tokenService.isTokenExpired())) {
                console.log('[AUTH] Restoring session: attempting token refresh');
                try {
                    await tokenService.refreshAccessToken();
                    console.log('[AUTH] Session restored successfully');
                } catch (err) {
                    console.error('[AUTH] Session restore failed, clearing auth data');
                    tokenService.clearAccessToken();
                    localStorage.removeItem('user');
                    setUser(null);
                }
            }
        };

        restoreSession();
    }, []);

    const handleLogin = async (email: string, password: string) => {
        setIsLoading(true);
        setError('');
        try {
            // Check for test user credentials
            if (email === TEST_CREDENTIALS.email && password === TEST_CREDENTIALS.password) {
                console.log('[AUTH] Using test user - bypassing backend');
                // Create mock token for test user
                const mockToken = 'mock_test_token_' + Date.now();
                tokenService.setAccessToken(mockToken, 3600);
                localStorage.setItem('user', JSON.stringify(TEST_USER));
                setUser(TEST_USER);
                return;
            }

            // Normal backend login
            const response = await login({ email, password });
            setUser(response.user);
        } catch (err: any) {
            setError(err.message || 'Login failed');
            throw err;
        } finally {
            setIsLoading(false);
        }
    };

    const handleRegister = async (username: string, email: string, password: string) => {
        setIsLoading(true);
        setError('');
        try {
            const response = await register({ username, email, password });
            setUser(response.user);
        } catch (err: any) {
            setError(err.message || 'Registration failed');
            throw err;
        } finally {
            setIsLoading(false);
        }
    };

    const handleLogout = async () => {
        try {
            await apiLogout();
        } catch (err) {
            console.error('[AUTH] Logout error:', err);
        } finally {
            tokenService.clearAccessToken();
            setUser(null);
        }
    };

    const clearError = () => {
        setError('');
    };

    return (
        <AuthContext.Provider
            value={{
                user,
                login: handleLogin,
                register: handleRegister,
                logout: handleLogout,
                isLoading,
                error,
                clearError,
            }}
        >
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};
