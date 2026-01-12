import { User, Bot } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';

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
  timestamp?: string; // Optional for compatibility if needed, but we use created_at
}

interface ChatMessageProps {
  message: Message;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.sender === 'user';
  
  // Debug: log message to check if markdown is being received
  if (!isUser) {
    console.log('[ChatMessage] Bot message:', {
      sender: message.sender,
      hasMarkdown: message.content.includes('**'),
      contentPreview: message.content.substring(0, 100)
    });
  }

  const formatTime = (dateString: string) => {
    if (!dateString) return '';
    try {
        const date = new Date(dateString);
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (e) {
        return '';
    }
  };

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
          {isUser ? (
            <p className="whitespace-pre-wrap leading-relaxed">
              {message.content}
            </p>
          ) : (
            <div className="prose prose-sm max-w-none">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeRaw]}
                components={{
                  p: ({node, ...props}) => <p className="mb-3 last:mb-0 leading-relaxed" {...props} />,
                  ul: ({node, ...props}) => <ul className="list-disc pl-5 mb-3 space-y-1.5" {...props} />,
                  ol: ({node, ...props}) => <ol className="list-decimal pl-5 mb-3 space-y-1.5" {...props} />,
                  li: ({node, ...props}) => <li className="leading-relaxed" {...props} />,
                  strong: ({node, ...props}) => <strong className="font-semibold text-foreground" {...props} />,
                  em: ({node, ...props}) => <em className="italic" {...props} />,
                  code: ({node, className, children, ...props}) => {
                    const inline = !className?.includes('language-');
                    return inline ? (
                      <code className="bg-slate-100 px-1.5 py-0.5 rounded text-sm font-mono" {...props}>{children}</code>
                    ) : (
                      <code className="block bg-slate-100 p-3 rounded-lg text-sm font-mono overflow-x-auto" {...props}>{children}</code>
                    );
                  },
                  pre: ({node, ...props}) => <pre className="mb-3 last:mb-0" {...props} />,
                  h1: ({node, ...props}) => <h1 className="text-xl font-bold mb-3 mt-2" {...props} />,
                  h2: ({node, ...props}) => <h2 className="text-lg font-bold mb-3 mt-2" {...props} />,
                  h3: ({node, ...props}) => <h3 className="text-base font-bold mb-2 mt-1" {...props} />,
                  hr: ({node, ...props}) => <hr className="my-4 border-t border-border" {...props} />,
                  blockquote: ({node, ...props}) => <blockquote className="border-l-4 border-primary/30 pl-4 italic my-3" {...props} />,
                  a: ({node, ...props}) => <a className="text-primary hover:underline" target="_blank" rel="noopener noreferrer" {...props} />,
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </div>
        <span className="text-xs text-muted-foreground/70 mt-2 px-1">
          {message.timestamp ? message.timestamp : formatTime(message.created_at)}
        </span>
      </div>
    </div>
  );
}
