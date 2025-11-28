import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';

type AuthMode = 'login' | 'register';

const LoginPage: React.FC = () => {
    const { login, register, isLoading, error, clearError } = useAuth();
    const navigate = useNavigate();
    const [authMode, setAuthMode] = useState<AuthMode>('login');

    const handleAuth = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        clearError();

        const formData = new FormData(e.currentTarget);
        const email = formData.get('email') as string;
        const password = formData.get('password') as string;

        try {
            if (authMode === 'register') {
                const username = formData.get('username') as string;
                await register(username, email, password);
            } else {
                await login(email, password);
            }
            navigate('/');
        } catch (err) {
            // Error is handled by AuthContext
        }
    };

    return (
        <div className="auth-container">
            <div className="auth-box">
                <div className="auth-header">
                    <h1>💚 Mental Health Support</h1>
                    <p>Your confidential companion for mental wellness</p>
                </div>

                <div className="auth-tabs">
                    <button
                        className={`auth-tab ${authMode === 'login' ? 'active' : ''}`}
                        onClick={() => {
                            setAuthMode('login');
                            clearError();
                        }}
                    >
                        Login
                    </button>
                    <button
                        className={`auth-tab ${authMode === 'register' ? 'active' : ''}`}
                        onClick={() => {
                            setAuthMode('register');
                            clearError();
                        }}
                    >
                        Register
                    </button>
                </div>

                <form onSubmit={handleAuth} className="auth-form">
                    {authMode === 'register' && (
                        <div className="form-group">
                            <label htmlFor="username">Username</label>
                            <input
                                id="username"
                                name="username"
                                type="text"
                                required
                                minLength={3}
                                placeholder="Choose a username"
                            />
                        </div>
                    )}

                    <div className="form-group">
                        <label htmlFor="email">Email</label>
                        <input
                            id="email"
                            name="email"
                            type="email"
                            required
                            placeholder="your@email.com"
                        />
                    </div>

                    <div className="form-group">
                        <label htmlFor="password">Password</label>
                        <input
                            id="password"
                            name="password"
                            type="password"
                            required
                            minLength={6}
                            placeholder="Enter your password"
                        />
                    </div>

                    {error && <div className="auth-error">{error}</div>}

                    <button type="submit" className="auth-submit" disabled={isLoading}>
                        {isLoading ? 'Please wait...' : authMode === 'login' ? 'Login' : 'Register'}
                    </button>
                </form>
            </div>
        </div>
    );
};

export default LoginPage;
