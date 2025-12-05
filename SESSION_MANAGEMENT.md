# Session Management Updates

## Tổng quan các thay đổi

Đã cập nhật hệ thống quản lý session để:

1. **Reset thời gian access token khi có hoạt động**: Mỗi khi người dùng tương tác với UI hoặc gọi API, session sẽ được gia hạn tự động
2. **Xử lý session expired đúng cách**: Khi session hết hạn do không hoạt động, hiển thị modal cho phép người dùng đăng nhập lại
3. **Đồng bộ timeout giữa frontend và backend**: Inactivity timeout tự động lấy từ `ACCESS_TOKEN_EXPIRE_MINUTES` của backend, đảm bảo nhất quán

### Lợi ích của việc đồng bộ timeout:

✅ **Nhất quán**: Frontend và backend luôn sử dụng cùng một thời gian timeout  
✅ **Dễ quản lý**: Chỉ cần thay đổi `ACCESS_TOKEN_EXPIRE_MINUTES` ở một nơi (backend)  
✅ **Dễ test**: Có thể override bằng biến môi trường `VITE_INACTIVITY_TIMEOUT_MINUTES` khi cần test  
✅ **Tránh lỗi**: Không còn tình trạng frontend timeout khác backend timeout

## Chi tiết thay đổi

### 1. Frontend - Token Service (`tokenService.ts`)

**Thay đổi chính:**
- Thay đổi từ auto-refresh timer sang activity-based refresh
- Thêm `resetActivityTimer()` - được gọi mỗi khi có hoạt động
- **Inactivity timeout tự động đồng bộ với backend**: Sử dụng thời gian từ `ACCESS_TOKEN_EXPIRE_MINUTES`
- Có thể override bằng biến môi trường `VITE_INACTIVITY_TIMEOUT_MINUTES` để test
- **Token refresh**: Chỉ refresh khi access token hết hạn (gặp lỗi 401) và có refresh token hợp lệ

**Cơ chế hoạt động:**
```
1. User Activity → resetActivityTimer() → Reset inactivity timeout
2. API Request → Access Token Expired? → 401 Error
3. Response Interceptor → Catch 401 → Call Refresh Token API
4. If Refresh Success → Retry Original Request
5. If Refresh Fail → Logout (Session Expired)
```

### 2. Frontend - API Interceptor (`api.ts`)

**Thay đổi:**
- Thêm `tokenService.resetActivityTimer()` vào request interceptor
- Mỗi API call sẽ reset activity timer → gia hạn session

### 3. Frontend - Activity Tracker (`useActivityTracker.ts`)

**File mới:**
- Custom hook theo dõi hoạt động người dùng
- Lắng nghe các sự kiện: mousedown, mousemove, keypress, scroll, touchstart, click
- Debounce 1 giây để tránh gọi quá nhiều
- Tự động reset activity timer khi có hoạt động

### 4. Frontend - Auth Context (`AuthContext.tsx`)

**Thay đổi:**
- `renewSession()`: Clear toàn bộ auth state trước khi redirect về login
- `dismissSessionExpiry()`: Gọi logout đúng cách
- Đảm bảo người dùng có thể đăng nhập lại sau khi session expired

### 5. Frontend - App Component (`App.tsx`)

**Thay đổi:**
- Thêm `useActivityTracker()` hook vào AppContent
- Cập nhật message trong SessionExpiryModal để rõ ràng hơn

### 6. Backend - Environment Config (`.env`)

**Thay đổi:**
- Thêm `ACCESS_TOKEN_EXPIRE_MINUTES=15`
- Thêm `REFRESH_TOKEN_EXPIRE_DAYS=7`
- Access token có thời gian sống 15 phút (khớp với inactivity timeout)

## Luồng hoạt động

### Khi người dùng đang hoạt động:

1. User tương tác với UI (click, type, scroll, etc.)
2. `useActivityTracker` detect activity
3. Gọi `tokenService.resetActivityTimer()`
4. Timer 15 phút được reset
5. Nếu token đã qua 50% lifetime → refresh token tự động
6. Session được gia hạn

### Khi người dùng gọi API:

1. API request được gửi
2. Request interceptor gọi `tokenService.resetActivityTimer()`
3. Timer 15 phút được reset
4. Nếu token sắp hết hạn → refresh trước khi gửi request
5. Session được gia hạn

### Khi session hết hạn (15 phút không hoạt động):

1. Inactivity timer hết hạn
2. `handleSessionExpiry()` được gọi
3. Clear access token
4. Dispatch event 'sessionExpired'
5. AuthContext nhận event → set `sessionExpired = true`
6. SessionExpiryModal hiển thị
7. User chọn:
   - **"Log In Again"**: Clear state → redirect về login → có thể đăng nhập lại
   - **"Dismiss"**: Logout và clear state

## Testing

Để test các tính năng:

1. **Test lazy refresh:**
   - Đăng nhập
   - Chờ token hết hạn (hoặc chỉnh timeout ngắn)
   - Thực hiện một hành động (VD: gửi tin nhắn)
   - Request đầu tiên sẽ fail (401)
   - Hệ thống tự động refresh token và retry request thành công
   - Kiểm tra console logs: `[API] 401 error, attempting token refresh...`

2. **Test inactivity timeout:**
   - Đăng nhập
   - Không tương tác trong 15 phút
   - Modal "Session Expired" sẽ hiển thị
   - Click "Log In Again" → có thể đăng nhập lại

3. **Test API-based refresh:**
   - Đăng nhập
   - Gọi API (send message, get conversations, etc.)
   - Kiểm tra console logs: `[API] Token expiring soon, refreshing...`
   - Session được gia hạn

## Lưu ý

- **Inactivity timeout**: Tự động đồng bộ với `ACCESS_TOKEN_EXPIRE_MINUTES` từ backend
  - Mặc định: Sử dụng thời gian từ token expiry (hiện tại là 15 phút)
  - Override cho testing: Tạo file `frontend/.env` và set `VITE_INACTIVITY_TIMEOUT_MINUTES=1` (1 phút)
- **Access token lifetime**: 15 phút (thay đổi trong `backend/.env` → `ACCESS_TOKEN_EXPIRE_MINUTES`)
- **Refresh token lifetime**: 7 ngày
- **Cơ chế Refresh**: Lazy refresh (chỉ refresh khi gặp lỗi 401 Unauthorized)

### Cách test với timeout ngắn:

1. Tạo file `frontend/.env`:
   ```bash
   VITE_API_URL=http://localhost:8000
   VITE_INACTIVITY_TIMEOUT_MINUTES=1
   ```

2. Restart frontend dev server

3. Đăng nhập và không tương tác trong 1 phút → modal sẽ hiển thị

## Troubleshooting

Nếu gặp lỗi khi đăng nhập lại sau session expired:
1. Kiểm tra console logs
2. Đảm bảo refresh token cookie vẫn còn valid
3. Clear browser cache và cookies nếu cần
4. Restart backend server để load config mới



Lỗi mất đồng bộ
Sửa state của UI khi gửi tin nhắn room này nhưng nhảy qua room khác