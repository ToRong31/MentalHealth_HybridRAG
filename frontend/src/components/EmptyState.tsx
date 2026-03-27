import { Heart, Brain, Coffee } from 'lucide-react';

interface EmptyStateProps {
  onNewChat: () => void;
}

export function EmptyState({ onNewChat }: EmptyStateProps) {
  const suggestions = [
    {
      icon: Heart,
      title: 'Quản lý cảm xúc',
      description: 'Chia sẻ cảm xúc và tìm cách điều tiết',
      prompt: 'Tôi đang cảm thấy lo lắng và căng thẳng',
      gradient: 'from-rose-500/10 to-pink-500/10'
    },
    {
      icon: Brain,
      title: 'Stress & áp lực',
      description: 'Giảm căng thẳng, cân bằng tinh thần',
      prompt: 'Làm sao để giảm stress công việc?',
      gradient: 'from-purple-500/10 to-indigo-500/10'
    },
    {
      icon: Coffee,
      title: 'Đồng hành chia sẻ',
      description: 'Ngày hôm nay của bạn thế nào',
      prompt: 'Tâm trang của tôi hôm nay hơi tệ',
      gradient: 'from-amber-500/10 to-orange-500/10'
    }
  ];

  return (
    <div className="h-full flex items-center justify-center p-8">
      <div className="max-w-3xl w-full text-center">
        {/* Icon */}
        <div className="inline-flex items-center justify-center w-24 h-24 rounded-3xl bg-gradient-to-br from-primary/10 via-accent/5 to-cyan-50 mb-8 relative">
          <div className="absolute inset-0 rounded-3xl bg-gradient-to-br from-primary/20 to-accent/20 blur-xl"></div>
          <Heart className="w-12 h-12 text-primary relative z-10" strokeWidth={2} />
        </div>

        {/* Heading */}
        <h2 className="text-3xl font-semibold text-foreground mb-3">
          Bạn muốn chia sẻ điều gì?
        </h2>
        <p className="text-muted-foreground text-lg mb-14 max-w-xl mx-auto leading-relaxed">
          Đây là không gian an toàn của bạn. Hãy thoải mái chia sẻ những suy nghĩ, 
          cảm xúc hay bất kỳ điều gì đang băn khoăn.
        </p>

        {/* Suggestion Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {suggestions.map((suggestion, index) => {
            const Icon = suggestion.icon;
            return (
              <button
                key={index}
                onClick={() => {
                  // In a real app, this would pre-fill the composer
                  onNewChat();
                }}
                className="p-6 rounded-2xl border-2 border-border bg-card hover:bg-gradient-to-br hover:from-muted/30 hover:to-transparent hover:border-primary/30 transition-all duration-300 text-left group hover:shadow-lg hover:scale-105"
              >
                <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${suggestion.gradient} flex items-center justify-center mb-4 group-hover:scale-110 transition-transform duration-300`}>
                  <Icon className="w-6 h-6 text-foreground/70" strokeWidth={2} />
                </div>
                <h3 className="font-semibold text-foreground mb-2">
                  {suggestion.title}
                </h3>
                <p className="text-sm text-muted-foreground mb-3 leading-relaxed">
                  {suggestion.description}
                </p>
                <p className="text-xs text-muted-foreground/70 italic">
                  "{suggestion.prompt}"
                </p>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
