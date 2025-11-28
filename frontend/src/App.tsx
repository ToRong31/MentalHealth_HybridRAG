import { useState, useRef, useEffect } from 'react'
import './App.css'
import {
  register,
  login,
  logout,
  getStoredUser,
  getConversations,
  getConversation,
  createConversation,
  deleteConversation,
  sendMessage
} from './api'
import type { User, Conversation, Message as MessageType, ConversationWithMessages } from './types'

type AuthMode = 'login' | 'register';

function App() {
  // Authentication state
  const [user, setUser] = useState<User | null>(getStoredUser())
  const [authMode, setAuthMode] = useState<AuthMode>('login')
  const [authLoading, setAuthLoading] = useState(false)
  const [authError, setAuthError] = useState('')

  // Conversation state
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [currentConversation, setCurrentConversation] = useState<ConversationWithMessages | null>(null)
  const [messages, setMessages] = useState<MessageType[]>([])

  // Chat state
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // UI state
  const [sidebarOpen, setSidebarOpen] = useState(true)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Load conversations on mount if authenticated
  useEffect(() => {
    if (user) {
      loadConversations()
    }
  }, [user])

  const loadConversations = async () => {
    try {
      const convs = await getConversations()
      setConversations(convs)
    } catch (error) {
      console.error('Error loading conversations:', error)
    }
  }

  const handleAuth = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setAuthLoading(true)
    setAuthError('')

    const formData = new FormData(e.currentTarget)
    const email = formData.get('email') as string
    const password = formData.get('password') as string

    try {
      if (authMode === 'register') {
        const username = formData.get('username') as string
        const response = await register({ username, email, password })
        setUser(response.user)
      } else {
        const response = await login({ email, password })
        setUser(response.user)
      }
    } catch (error: any) {
      setAuthError(error.message || 'Authentication failed')
    } finally {
      setAuthLoading(false)
    }
  }

  const handleLogout = () => {
    logout()
    setUser(null)
    setConversations([])
    setCurrentConversation(null)
    setMessages([])
  }

  const handleNewConversation = async () => {
    try {
      const title = `New Chat ${new Date().toLocaleString()}`
      const conversation = await createConversation(title)
      setConversations([conversation, ...conversations])
      setCurrentConversation({ ...conversation, messages: [] })
      setMessages([])
    } catch (error) {
      console.error('Error creating conversation:', error)
    }
  }

  const handleSelectConversation = async (conversationId: number) => {
    try {
      const conversation = await getConversation(conversationId)
      setCurrentConversation(conversation)
      setMessages(conversation.messages)
    } catch (error) {
      console.error('Error loading conversation:', error)
    }
  }

  const handleDeleteConversation = async (conversationId: number) => {
    if (!confirm('Are you sure you want to delete this conversation?')) return

    try {
      await deleteConversation(conversationId)
      setConversations(conversations.filter(c => c.id !== conversationId))
      if (currentConversation?.id === conversationId) {
        setCurrentConversation(null)
        setMessages([])
      }
    } catch (error) {
      console.error('Error deleting conversation:', error)
    }
  }

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isLoading) return

    const userMessageContent = inputValue
    setInputValue('')
    setIsLoading(true)

    // Optimistically add user message to UI
    const tempUserMessage: MessageType = {
      id: Date.now(),
      conversation_id: currentConversation?.id || 0,
      content: userMessageContent,
      sender: 'user',
      is_high_risk: false,
      is_mental_health_related: true,
      created_at: new Date().toISOString()
    }
    setMessages(prev => [...prev, tempUserMessage])

    try {
      const response = await sendMessage({
        message: userMessageContent,
        conversation_id: currentConversation?.id,
        conversation_title: currentConversation ? undefined : `Chat ${new Date().toLocaleString()}`
      })

      // If this was a new conversation, update state
      if (!currentConversation) {
        await loadConversations()
        const newConv = await getConversation(response.conversation_id)
        setCurrentConversation(newConv)
        setMessages(newConv.messages)
      } else {
        // Add bot message
        const botMessage: MessageType = {
          id: response.message_id,
          conversation_id: response.conversation_id,
          content: response.answer,
          sender: 'bot',
          is_high_risk: response.is_high_risk,
          is_mental_health_related: response.is_mental_health_related,
          created_at: new Date().toISOString()
        }
        setMessages(prev => [...prev, botMessage])

        // Update conversation list
        await loadConversations()
      }
    } catch (error) {
      console.error('Error sending message:', error)
      const errorMessage: MessageType = {
        id: Date.now() + 1,
        conversation_id: currentConversation?.id || 0,
        content: 'Sorry, I encountered an error. Please try again.',
        sender: 'bot',
        is_high_risk: false,
        is_mental_health_related: false,
        created_at: new Date().toISOString()
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  // Render login/register form if not authenticated
  if (!user) {
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
                setAuthMode('login')
                setAuthError('')
              }}
            >
              Login
            </button>
            <button
              className={`auth-tab ${authMode === 'register' ? 'active' : ''}`}
              onClick={() => {
                setAuthMode('register')
                setAuthError('')
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

            {authError && <div className="auth-error">{authError}</div>}

            <button type="submit" className="auth-submit" disabled={authLoading}>
              {authLoading ? 'Please wait...' : authMode === 'login' ? 'Login' : 'Register'}
            </button>
          </form>
        </div>
      </div>
    )
  }

  // Render main chat interface
  return (
    <div className="app-container">
      {/* Sidebar */}
      <div className={`sidebar ${sidebarOpen ? 'open' : 'closed'}`}>
        <div className="sidebar-header">
          <h2>💚 Conversations</h2>
          <button className="btn-icon" onClick={() => setSidebarOpen(!sidebarOpen)}>
            {sidebarOpen ? '◀' : '▶'}
          </button>
        </div>

        <button className="btn-new-chat" onClick={handleNewConversation}>
          + New Conversation
        </button>

        <div className="conversation-list">
          {conversations.map(conv => (
            <div
              key={conv.id}
              className={`conversation-item ${currentConversation?.id === conv.id ? 'active' : ''}`}
              onClick={() => handleSelectConversation(conv.id)}
            >
              <div className="conversation-title">{conv.title}</div>
              <div className="conversation-date">
                {new Date(conv.updated_at).toLocaleDateString()}
              </div>
              <button
                className="btn-delete"
                onClick={(e) => {
                  e.stopPropagation()
                  handleDeleteConversation(conv.id)
                }}
              >
                🗑️
              </button>
            </div>
          ))}
        </div>

        <div className="sidebar-footer">
          <div className="user-info">
            <span>{user.username}</span>
          </div>
          <button className="btn-logout" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </div>

      {/* Main chat area */}
      <div className="chat-container">
        <div className="chat-header">
          <div className="header-content">
            <h1>{currentConversation?.title || 'Select or create a conversation'}</h1>
            <p>Your confidential companion for mental wellness</p>
          </div>
        </div>

        <div className="chat-messages">
          {messages.length === 0 && !currentConversation && (
            <div className="welcome-message">
              <h2>Welcome to Mental Health Support! 💚</h2>
              <p>Start a new conversation to begin chatting</p>
            </div>
          )}

          {messages.map((message) => (
            <div
              key={message.id}
              className={`message ${message.sender === 'user' ? 'message-user' : 'message-bot'} ${message.is_high_risk ? 'message-high-risk' : ''}`}
            >
              <div className="message-content">
                <div className="message-text">{message.content}</div>
                <div className="message-time">
                  {new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="message message-bot">
              <div className="message-content">
                <div className="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="chat-input-container">
          <div className="chat-input-wrapper">
            <input
              type="text"
              className="chat-input"
              placeholder="Type your message here..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={isLoading}
            />
            <button
              className="send-button"
              onClick={handleSendMessage}
              disabled={isLoading || !inputValue.trim()}
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <line x1="22" y1="2" x2="11" y2="13"></line>
                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
