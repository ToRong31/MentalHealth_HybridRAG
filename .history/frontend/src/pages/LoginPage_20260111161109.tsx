import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { ImageWithFallback } from '../components/figma/ImageWithFallback';
import { Heart, Shield, Sparkles, AlertCircle } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '../components/ui/alert';

export default function LoginPage() {
  const { login, register, isLoading, error, clearError } = useAuth();
  const navigate = useNavigate();
  const [isLogin, setIsLogin] = useState(true);
  
  // Controlled inputs for clearer logic integration
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [username, setUsername] = useState('');
  // const [authMode, setAuthMode] = useState<'login' | 'register'>('login'); // Mapped to isLogin

  const handleToggleMode = (mode: boolean) => {
    setIsLogin(mode);
    clearError();
    setEmail('');
    setPassword('');
    setUsername('');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();
    try {
        if (isLogin) {
            await login(email, password);
        } else {
            await register(username, email, password);
        }
        // Navigation might be handled by AuthContext or separate effect, but usually navigate here or in context
        // Keeping it simple, if context handles it, great. If not, redirect.
        // navigate('/'); 
    } catch (err) {
        // Error handled by context 'error' state usually
    }
  };

  return (
    <div className="flex min-h-screen">
      {/* Left Hero Panel - 60% */}
      <div className="hidden lg:flex lg:w-3/5 relative overflow-hidden bg-gradient-to-br from-emerald-50 via-teal-50/30 to-green-50">
        <div className="absolute inset-0 z-0">
          <ImageWithFallback
            src="https://images.unsplash.com/photo-1722094250550-4993fa28a51b?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxwZWFjZWZ1bCUyMG1lZGl0YXRpb24lMjB3ZWxsbmVzc3xlbnwxfHx8fDE3NjgwMDc4MDl8MA&ixlib=rb-4.1.0&q=80&w=1080&utm_source=figma&utm_medium=referral"
            alt="MenChat Wellness"
            className="w-full h-full object-cover opacity-10"
          />
        </div>
        
        {/* Decorative gradient orbs */}
        <div className="absolute top-20 right-20 w-96 h-96 bg-gradient-to-br from-primary/20 to-accent/20 rounded-full blur-3xl"></div>
        <div className="absolute bottom-20 left-20 w-80 h-80 bg-gradient-to-tr from-emerald-200/30 to-teal-200/30 rounded-full blur-3xl"></div>
        
        <div className="relative z-10 flex flex-col justify-center px-16 xl:px-24">
          {/* Logo Placeholder */}
          <div className="mb-12">
            <div className="flex items-center gap-3">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-primary to-accent flex items-center justify-center shadow-lg shadow-primary/20">
                <Heart className="w-7 h-7 text-white" />
              </div>
              <span className="text-2xl font-semibold text-foreground">MenChat</span>
            </div>
          </div>

          {/* Slogan */}
          <h1 className="text-5xl font-semibold mb-6 text-foreground leading-tight">
            Tâm lý khỏe mạnh,<br />
            <span className="bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
              cuộc sống hạnh phúc
            </span>
          </h1>
          
          <p className="text-lg text-muted-foreground max-w-md leading-relaxed mb-12">
            Không gian riêng tư và an toàn để bạn chia sẻ tâm tư, 
            cảm xúc. Chúng tôi luôn lắng nghe và đồng hành cùng bạn.
          </p>

          {/* Feature highlights */}
          <div className="space-y-5">
            {[
              { 
                icon: Shield, 
                title: 'Bảo mật tuyệt đối', 
                description: 'Mọi cuộc trò chuyện được mã hóa và bảo vệ',
                gradient: 'from-blue-500/10 to-indigo-500/10'
              },
              { 
                icon: Heart, 
                title: 'Tư vấn chuyên nghiệp', 
                description: 'Lắng nghe và hỗ trợ với sự đồng cảm',
                gradient: 'from-rose-500/10 to-pink-500/10'
              },
              { 
                icon: Sparkles, 
                title: 'Luôn sẵn sàng', 
                description: 'Hỗ trợ 24/7 mọi lúc bạn cần',
                gradient: 'from-amber-500/10 to-orange-500/10'
              }
            ].map((feature, index) => {
              const Icon = feature.icon;
              return (
                <div key={index} className="flex items-start gap-4 group">
                  <div className={`relative w-14 h-14 rounded-2xl bg-gradient-to-br ${feature.gradient} backdrop-blur-sm flex items-center justify-center shadow-sm border border-white/40 group-hover:scale-105 transition-transform duration-200`}>
                    <Icon className="w-6 h-6 text-foreground/70" strokeWidth={2} />
                  </div>
                  <div className="flex-1 pt-1">
                    <div className="font-semibold text-foreground mb-1">{feature.title}</div>
                    <div className="text-sm text-muted-foreground">{feature.description}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Right Login Panel - 40% */}
      <div className="flex-1 flex items-center justify-center p-8 bg-white">
        <div className="w-full max-w-md">
          {/* Mobile Logo */}
          <div className="lg:hidden mb-8 text-center">
            <div className="inline-flex items-center gap-3 mb-4">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-primary to-accent flex items-center justify-center shadow-lg shadow-primary/20">
                <Heart className="w-7 h-7 text-white" />
              </div>
              <span className="text-2xl font-semibold text-foreground">MenChat</span>
            </div>
          </div>

          {/* Tab Toggle */}
          <div className="flex gap-1 p-1 bg-secondary/50 rounded-2xl mb-8">
            <button
              onClick={() => handleToggleMode(true)}
              className={`flex-1 py-3 rounded-xl transition-all duration-200 ${
                isLogin 
                  ? 'bg-white shadow-md text-foreground font-semibold' 
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              Đăng nhập
            </button>
            <button
              onClick={() => handleToggleMode(false)}
              className={`flex-1 py-3 rounded-xl transition-all duration-200 ${
                !isLogin 
                  ? 'bg-white shadow-md text-foreground font-semibold' 
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              Đăng ký
            </button>
          </div>

          {/* Form Title */}
          <div className="mb-8">
            <h2 className="text-2xl font-semibold text-foreground mb-2">
              {isLogin ? 'Chào mừng trở lại' : 'Tạo tài khoản mới'}
            </h2>
            <p className="text-muted-foreground">
              {isLogin 
                ? 'Tiếp tục hành trình chăm sóc sức khỏe tinh thần của bạn' 
                : 'Bắt đầu hành trình chăm sóc bản thân ngay hôm nay'}
            </p>
          </div>

          {/* Error Alert */}
          {error && (
            <Alert variant="destructive" className="mb-6">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Lỗi</AlertTitle>
                <AlertDescription>
                {error}
                </AlertDescription>
            </Alert>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            {!isLogin && (
                <div className="space-y-2">
                <label htmlFor="username" className="text-sm font-semibold text-foreground">
                    Tên đăng nhập
                </label>
                <Input
                    id="username"
                    name="username"
                    type="text"
                    placeholder="TenCuaBan"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="h-12 px-4 rounded-xl border-2 border-border bg-input-background focus:border-primary focus:ring-0 transition-all duration-200 placeholder:text-muted-foreground/50"
                    required
                />
                </div>
            )}

            <div className="space-y-2">
              <label htmlFor="email" className="text-sm font-semibold text-foreground">
                Địa chỉ email
              </label>
              <Input
                id="email"
                name="email"
                type="email"
                placeholder="ten@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="h-12 px-4 rounded-xl border-2 border-border bg-input-background focus:border-primary focus:ring-0 transition-all duration-200 placeholder:text-muted-foreground/50"
                required
              />
            </div>
            
            <div className="space-y-2">
              <label htmlFor="password" className="text-sm font-semibold text-foreground">
                Mật khẩu
              </label>
              <Input
                id="password"
                name="password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="h-12 px-4 rounded-xl border-2 border-border bg-input-background focus:border-primary focus:ring-0 transition-all duration-200 placeholder:text-muted-foreground/50"
                required
              />
            </div>

            <Button
              type="submit"
              disabled={isLoading || !email || !password || (!isLogin && !username)}
              className="w-full h-12 bg-gradient-to-r from-primary to-accent hover:shadow-lg hover:shadow-primary/25 text-primary-foreground rounded-xl transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:shadow-none font-semibold"
            >
              {isLoading ? 'Đang xử lý...' : (isLogin ? 'Tiếp tục' : 'Tạo tài khoản')}
            </Button>
          </form>

          {/* Footer Links */}
          <div className="mt-8 text-center">
            <button 
              onClick={() => navigate('/')}
              className="text-sm text-muted-foreground hover:text-primary transition-colors duration-200"
            >
              ← Quay lại trang chủ
            </button>
          </div>

          {/* Terms */}
          <p className="mt-8 text-xs text-center text-muted-foreground leading-relaxed">
            Bằng việc tiếp tục, bạn đồng ý với{' '}
            <a href="#" className="text-primary hover:underline font-medium">
              Điều khoản sử dụng
            </a>
            {' '}và{' '}
            <a href="#" className="text-primary hover:underline font-medium">
              Chính sách bảo mật
            </a>
            {' '}của chúng tôi
          </p>
        </div>
      </div>
    </div>
  );
}
