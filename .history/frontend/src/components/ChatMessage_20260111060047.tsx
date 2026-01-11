import { User, Bot } from 'lucide-react';

export interface Message {
  id: number | string;
  conversation_id: number;
  content: string;
  sender: 'user' | 'bot';
  is_high_risk?: boolean;
  is_mental_health_related?: boolean;
  created_at: string;
  isPending?: boolean;
  tempId?: string;
}

interface ChatMessageProps {
  message: Message;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.sender === 'user';

  return (
    <div className={`flex gap-4 mb-6 ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 ${
        isUser 
          ? 'bg-gradient-to-br from-primary to-accent shadow-sm shadow-primary/20' 
          : 'bg-gradient-to-br from-slate-100 to-slate-50 border border-border'
      }`}>
        {isUser ? (
          <User className="w-5 h-5 text-white" />
        ) : (
          <Bot className="w-5 h-5 text-muted-foreground" />
        )}
      </div>

      {/* Message Bubble */}
      <div className={`flex-1 max-w-[75%] ${isUser ? 'flex flex-col items-end' : ''}`}>
        <div className={`rounded-2xl px-5 py-3.5 shadow-sm ${
          isUser 
            ? 'bg-gradient-to-br from-emerald-50 to-teal-50/50 text-foreground rounded-tr-md border border-primary/10' 
            : 'bg-white text-foreground rounded-tl-md border border-border'
        }`}>
          <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
          {message.isPending && (
            <span className="text-xs text-muted-foreground ml-2">(Đang gửi...)</span>
          )}
        </div>
        <span className="text-xs text-muted-foreground/70 mt-2 px-1">
          {new Date(message.created_at).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>
    </div>
  );
}
