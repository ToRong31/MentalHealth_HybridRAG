import { Button } from './ui/button';
import { Plus, MessageSquare, LogOut, Trash2, Edit } from 'lucide-react';
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
  
  const handleRename = (e: React.MouseEvent, chatId: number, currentTitle: string) => {
    e.stopPropagation();
    const newTitle = prompt('Đổi tên cuộc trò chuyện:', currentTitle);
    if (newTitle && newTitle.trim()) {
      onRenameChat(chatId, newTitle.trim());
    }
  };

  const handleDelete = (e: React.MouseEvent, chatId: number) => {
    e.stopPropagation();
    if (window.confirm('Bạn có chắc chắn muốn xóa cuộc trò chuyện này?')) {
      onDeleteChat(chatId);
    }
  };

  const formatTime = (dateString?: string) => {
    if (!dateString) return '';
    
    // Parse date - xử lý cả ISO string và timestamp
    let date: Date;
    if (typeof dateString === 'string' && dateString.includes('T')) {
      // ISO format: "2024-01-12T10:30:00Z" hoặc "2024-01-12T10:30:00"
      date = new Date(dateString);
    } else {
      // Timestamp hoặc format khác
      date = new Date(dateString);
    }
    
    // Kiểm tra date hợp lệ
    if (isNaN(date.getTime())) return '';
    
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSecs = Math.floor(diffMs / 1000);
    const diffMins = Math.floor(diffSecs / 60);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    // Vừa xong
    if (diffSecs < 60) return 'Vừa xong';
    // Dưới 1 giờ
    if (diffMins < 60) return `${diffMins} phút trước`;
    // Dưới 24 giờ
    if (diffHours < 24) return `${diffHours} giờ trước`;
    // Hôm qua
    if (diffDays === 1) return 'Hôm qua';
    // Trong tuần
    if (diffDays < 7) return `${diffDays} ngày trước`;
    // Lâu hơn
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
            <div className="flex items-center gap-3 mb-4 cursor-pointer" onClick={onToggleCollapse}>
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
              <button
                key={chat.id}
                onClick={() => onChatSelect(chat.id)}
                className={`w-full text-left px-3 py-3 rounded-lg transition-all duration-200 group relative ${
                  activeChat === chat.id
                    ? 'bg-sidebar-accent text-sidebar-accent-foreground shadow-sm'
                    : 'hover:bg-sidebar-accent/50 text-sidebar-foreground'
                }`}
              >
                <div className="flex items-start gap-3">
                  <MessageSquare className={`w-4 h-4 mt-0.5 flex-shrink-0 ${
                    activeChat === chat.id ? 'text-primary' : 'text-muted-foreground'
                  }`} />
                  <div className="flex-1 min-w-0 pr-6">
                    <div className="font-medium truncate text-sm mb-1">
                      {chat.title}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {formatTime(chat.updated_at)}
                    </div>
                  </div>
                  
                  {/* Action Buttons */}
                  <div className={`absolute right-2 top-2 flex flex-col gap-1 ${activeChat === chat.id ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'} transition-opacity`}>
                    <div 
                        onClick={(e) => handleRename(e, chat.id, chat.title)}
                        className="p-1 hover:bg-background/80 rounded transition-colors text-muted-foreground hover:text-foreground"
                        title="Đổi tên"
                    >
                        <Edit className="w-3 h-3" />
                    </div>
                    <div 
                        onClick={(e) => handleDelete(e, chat.id)}
                        className="p-1 hover:bg-background/80 rounded transition-colors text-muted-foreground hover:text-destructive"
                        title="Xóa"
                    >
                        <Trash2 className="w-3 h-3" />
                    </div>
                  </div>
                </div>
              </button>
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
                    ? 'bg-sidebar-accent text-primary shadow-sm'
                    : 'text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground'
                }`}
                title={chat.title}
              >
                <MessageSquare className="w-5 h-5" />
              </button>
            ))}
             <button
                onClick={onToggleCollapse}
                className="w-10 h-10 rounded-lg flex items-center justify-center text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground mt-auto"
            >
                 <Plus className="w-5 h-5" /> 
            </button>
          </div>
        )}
      </div>

      {/* Footer / User Profile */}
      <div className="p-4 border-t border-sidebar-border mt-auto">
        {!isCollapsed ? (
             <div className="flex items-center gap-3 overflow-hidden">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary/20 to-accent/20 flex items-center justify-center flex-shrink-0 text-primary font-semibold text-xs">
                    {userEmail.substring(0, 2).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium truncate text-sidebar-foreground">{userEmail}</p>
                </div>
                <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-destructive" onClick={onLogout} title="Đăng xuất">
                    <LogOut className="w-4 h-4" />
                </Button>
             </div>
        ) : (
            <div className="flex justify-center">
                <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-destructive" onClick={onLogout} title="Đăng xuất">
                    <LogOut className="w-4 h-4" />
                </Button>
            </div>
        )}
      </div>
    </div>
  );
}
