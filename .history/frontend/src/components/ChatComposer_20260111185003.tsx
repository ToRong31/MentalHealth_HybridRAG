import { useRef, useEffect } from 'react';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { Send } from 'lucide-react';

interface ChatComposerProps {
  onSendMessage: (message: string) => void;
  disabled?: boolean;
  inputValue: string;
  onInputChange: (value: string) => void;
}

export function ChatComposer({ onSendMessage, disabled = false, inputValue, onInputChange }: ChatComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputValue.trim() && !disabled) {
      onSendMessage(inputValue.trim());
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const scrollHeight = textareaRef.current.scrollHeight;
      const maxHeight = 5 * 24; // 5 rows * 24px line height
      textareaRef.current.style.height = Math.min(scrollHeight, maxHeight) + 'px';
    }
  }, [inputValue]);

  return (
    <div className="border-t border-border bg-white/80 backdrop-blur-sm px-6 py-5">
      <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
        <div className="flex items-end gap-3">
          {/* Text Input */}
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={inputValue}
              onChange={(e) => onInputChange(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Chia sẻ suy nghĩ của bạn..."
              disabled={disabled}
              className="min-h-[44px] max-h-[120px] resize-none rounded-2xl border-2 border-border bg-input-background px-4 py-2.5 focus:border-primary focus:ring-0 transition-all duration-200 shadow-sm w-full text-base outline-none disabled:cursor-not-allowed disabled:opacity-50"
              rows={1}
            />
          </div>

          {/* Send Button */}
          <Button
            type="submit"
            disabled={!inputValue.trim() || disabled}
            className="h-[44px] w-[44px] p-0 rounded-2xl bg-gradient-to-r from-primary to-accent hover:shadow-lg hover:shadow-primary/25 text-primary-foreground transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:shadow-none flex-shrink-0"
            title="Gửi tin nhắn"
          >
            <Send className="w-5 h-5" />
          </Button>
        </div>
      </form>
    </div>
  );
}
