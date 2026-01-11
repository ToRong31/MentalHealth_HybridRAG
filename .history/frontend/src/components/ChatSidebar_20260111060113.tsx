import { Button } from './ui/button';
import { Plus, MessageSquare, LogOut, ChevronLeft, ChevronRight, User, Trash2, Edit } from 'lucide-react';
import type { Conversation } from '../types';

interface ChatSidebarProps {
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  activeChat: number | null;
  conversations: Conversation[];
  onChatSelect: (chatId: number) => void;
  onNewChat: () => void;
  onDeleteChat: (chatId: number) => void;
  onRenameChat: (chatId: number, newTitle: string) => void;
  onLogout: () => void;
  userEmail?: string;
}

export function ChatSidebar({ 
  isCollapsed, 
  onToggleCollapse, 
  activeChat, 
  conversations,
  onChatSelect,
  onNewChat,
  onDeleteChat,
  onRenameChat,
  onLogout,
  userEmail = 'user@example.com'
}: ChatSidebarProps) {
  const handleRename = (chatId: number, currentTitle: string) => {
    const newTitle = prompt('Đổi tên cuộc trò chuyện:', currentTitle);
    if (newTitle && newTitle.trim()) {
      onRenameChat(chatId, newTitle.trim());
    }
  };

  const formatTime = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 60) return `${diffMins} phút trước`;
    if (diffHours < 24) return `${diffHours} giờ trước`;
    if (diffDays === 1) return 'Hôm qua';
    if (diffDays < 7) return `${diffDays} ngày trước`;
    return date.toLocaleDateString('vi-VN');
  };

  return (
    <div 
      className={`bg-sidebar border-r border-sidebar-border h-full flex flex-col transition-all duration-300 ease-in-out ${
        isCollapsed ? 'w-[72px]' : 'w-[280px]'
      }`}
    >
      {/* Header */}
      <div className="p-4 border-b border-sidebar-border">
        {!isCollapsed && (
          <div className="mb-4">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-accent flex items-center justify-center flex-shrink-0">
                <MessageSquare className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl font-semibold text-sidebar-foreground">MenChat</span>
            </div>
            <Button 
              className="w-full h-11 bg-primary hover:bg-primary/90 text-primary-foreground rounded-xl shadow-sm hover:shadow-md transition-all duration-200"
              onClick={onNewChat}
            >
              <Plus className="w-5 h-5 mr-2" />
              Trò chuyện mới
            </Button>
          </div>
        )}
        
        {isCollapsed && (
          <Button 
            className="w-full h-10 bg-primary hover:bg-primary/90 text-primary-foreground rounded-xl p-0 shadow-sm"
            onClick={onNewChat}
          >
            <Plus className="w-5 h-5" />
          </Button>
        )}
      </div>

      {/* Chat List */}
      <div className="flex-1 overflow-y-auto px-2 py-2">
        {!isCollapsed ? (
          <div className="space-y-1">
            {conversations.map((chat) => (
              <div
                key={chat.id}
                className={`group w-full text-left px-3 py-3 rounded-lg transition-all duration-200 ${
                  activeChat === chat.id
                    ? 'bg-sidebar-accent text-sidebar-accent-foreground shadow-sm'
                    : 'hover:bg-sidebar-accent/50 text-sidebar-foreground'
                }`}
              >
                <button
                  onClick={() => onChatSelect(chat.id)}
                  className="w-full text-left"
                >
                  <div className="flex items-start gap-3">
                    <MessageSquare className={`w-4 h-4 mt-0.5 flex-shrink-0 ${
                      activeChat === chat.id ? 'text-primary' : 'text-muted-foreground'
                    }`} />
                    <div className="flex-1 min-w-0">
                      <div className="font-medium truncate text-sm mb-1">
                        {chat.title}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {formatTime(chat.updated_at)}
                      </div>
                    </div>
                  </div>
                </button>
                {/* Action buttons - show on hover */}
                <div className="flex gap-1 mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRename(chat.id, chat.title);
                    }}
                    className="p-1.5 rounded hover:bg-sidebar-accent/70 text-muted-foreground hover:text-foreground transition-colors"
                    title="Đổi tên"
                  >
                    <Edit className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteChat(chat.id);
                    }}
                    className="p-1.5 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
                    title="Xóa"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-2 flex flex-col items-center">
            {conversations.slice(0, 5).map((chat) => (
              <button
                key={chat.id}
                onClick={() => onChatSelect(chat.id)}
                className={`w-10 h-10 rounded-lg flex items-center justify-center transition-all duration-200 ${
                  activeChat === chat.id
                    ? 'bg-sidebar-accent text-primary'
                    : 'hover:bg-sidebar-accent/50 text-muted-foreground'
                }`}
                title={chat.title}
              >
                <MessageSquare className="w-5 h-5" />
              </button>
            ))}
          </div>
        )}
      </div>

      {/* User Profile & Logout */}
      <div className="p-4 border-t border-sidebar-border">
        {!isCollapsed ? (
          <div className="space-y-3">
            <div className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-sidebar-accent/50 transition-colors cursor-pointer">
              <div className="w-9 h-9 rounded-full bg-gradient-to-br from-primary to-accent flex items-center justify-center flex-shrink-0">
                <User className="w-5 h-5 text-white" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-medium text-sm truncate">Người dùng</div>
                <div className="text-xs text-muted-foreground truncate">{userEmail}</div>
              </div>
            </div>
            <Button
              variant="outline"
              className="w-full justify-start h-10 rounded-lg border-border hover:bg-sidebar-accent hover:text-destructive hover:border-destructive/30 transition-all duration-200"
              onClick={onLogout}
            >
              <LogOut className="w-4 h-4 mr-2" />
              Đăng xuất
            </Button>
          </div>
        ) : (
          <div className="flex flex-col gap-2 items-center">
            <button
              className="w-10 h-10 rounded-full bg-gradient-to-br from-primary to-accent flex items-center justify-center"
              title="Người dùng"
            >
              <User className="w-5 h-5 text-white" />
            </button>
            <button
              className="w-10 h-10 rounded-lg hover:bg-destructive/10 hover:text-destructive transition-colors flex items-center justify-center"
              onClick={onLogout}
              title="Đăng xuất"
            >
              <LogOut className="w-5 h-5" />
            </button>
          </div>
        )}
      </div>

      {/* Collapse Toggle Button */}
      <button
        onClick={onToggleCollapse}
        className="absolute -right-3 top-6 w-6 h-6 rounded-full bg-white border border-border shadow-md flex items-center justify-center hover:bg-sidebar-accent transition-colors duration-200 z-10"
        title={isCollapsed ? 'Mở rộng' : 'Thu gọn'}
      >
        {isCollapsed ? (
          <ChevronRight className="w-4 h-4 text-muted-foreground" />
        ) : (
          <ChevronLeft className="w-4 h-4 text-muted-foreground" />
        )}
      </button>
    </div>
  );
}
