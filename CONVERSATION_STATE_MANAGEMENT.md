# Conversation State Management

## Tổng quan

Hệ thống quản lý state cho các cuộc hội thoại đã được cập nhật để đảm bảo mỗi cuộc hội thoại hoạt động độc lập. Điều này giải quyết vấn đề khi người dùng chuyển đổi giữa các cuộc hội thoại trong khi đang gửi tin nhắn.

## Vấn đề trước đây

Trước đây, state được quản lý global cho toàn bộ ứng dụng:
- `messages`: Mảng tin nhắn chung
- `inputValue`: Giá trị input chung
- `isLoading`: Trạng thái loading chung

**Hậu quả:**
- Khi đang gửi tin nhắn ở cuộc hội thoại A và chuyển sang cuộc hội thoại B
- UI hiển thị sai: cuộc hội thoại B hiển thị loading state của cuộc hội thoại A
- Khi response trả về, tin nhắn xuất hiện ở cuộc hội thoại B thay vì A

## Giải pháp mới

### 1. Per-Conversation State

Mỗi cuộc hội thoại có state riêng được lưu trong một Map:

```typescript
interface ConversationState {
    messages: Message[];      // Tin nhắn của cuộc hội thoại này
    inputValue: string;       // Giá trị input của cuộc hội thoại này
    isLoading: boolean;       // Trạng thái loading của cuộc hội thoại này
}

const [conversationStates, setConversationStates] = 
    useState<Map<number | 'new', ConversationState>>(new Map());
```

### 2. Key Management

- **Cuộc hội thoại đã tồn tại**: Sử dụng `conversationId` làm key
- **Cuộc hội thoại mới**: Sử dụng string `'new'` làm key tạm thời
- Khi cuộc hội thoại mới được tạo, state được chuyển từ key `'new'` sang `conversationId` thực

### 3. Helper Functions

#### `getCurrentState()`
Lấy state của cuộc hội thoại hiện tại:
```typescript
const getCurrentState = (): ConversationState => {
    const key = currentConversation?.id ?? 'new';
    return conversationStates.get(key) ?? {
        messages: [],
        inputValue: '',
        isLoading: false,
    };
};
```

#### `updateCurrentState()`
Cập nhật state của cuộc hội thoại hiện tại:
```typescript
const updateCurrentState = (updates: Partial<ConversationState>) => {
    const key = currentConversation?.id ?? 'new';
    const currentState = getCurrentState();
    const newState = { ...currentState, ...updates };
    setConversationStates(new Map(conversationStates.set(key, newState)));
};
```

## Luồng hoạt động

### Khi chọn cuộc hội thoại

1. Load dữ liệu cuộc hội thoại từ server
2. Kiểm tra xem đã có state cho cuộc hội thoại này chưa
3. Nếu chưa có: Khởi tạo state mới với messages từ server
4. Nếu đã có: Cập nhật messages từ server (giữ nguyên inputValue và isLoading)

```typescript
if (!conversationStates.has(conversationId)) {
    // Khởi tạo state mới
    const newState: ConversationState = {
        messages: conversation.messages,
        inputValue: '',
        isLoading: false,
    };
    setConversationStates(new Map(conversationStates.set(conversationId, newState)));
} else {
    // Cập nhật messages, giữ nguyên input và loading state
    updateCurrentState({ messages: conversation.messages });
}
```

### Khi gửi tin nhắn

1. Lấy state của cuộc hội thoại hiện tại
2. Lưu `conversationId` vào biến local để tránh bị thay đổi khi user chuyển cuộc hội thoại
3. Cập nhật state của cuộc hội thoại này (clear input, set loading)
4. Gửi request
5. Khi nhận response, cập nhật state dựa trên `conversationId` đã lưu, không phải `currentConversation`

```typescript
const handleSendMessage = async () => {
    const currentState = getCurrentState();
    const conversationIdForMessage = currentConversation?.id; // Lưu ID
    
    // Cập nhật state cho cuộc hội thoại này
    updateCurrentState({ 
        inputValue: '', 
        isLoading: true 
    });
    
    // ... gửi message ...
    
    // Cập nhật state dựa trên conversationIdForMessage, không phải currentConversation
    const key = conversationIdForMessage;
    const latestState = conversationStates.get(key) ?? currentState;
    // ... cập nhật state ...
};
```

### Khi xóa cuộc hội thoại

1. Xóa cuộc hội thoại từ server
2. Xóa state của cuộc hội thoại khỏi Map
3. Nếu đang xem cuộc hội thoại bị xóa, clear currentConversation

```typescript
const newStates = new Map(conversationStates);
newStates.delete(conversationId);
setConversationStates(newStates);
```

## Lợi ích

### 1. Độc lập giữa các cuộc hội thoại
- Mỗi cuộc hội thoại có state riêng
- Gửi tin nhắn ở cuộc hội thoại A không ảnh hưởng đến cuộc hội thoại B

### 2. Hỗ trợ gửi tin nhắn đồng thời
- Có thể gửi tin nhắn ở nhiều cuộc hội thoại cùng lúc
- Mỗi cuộc hội thoại hiển thị loading state riêng

### 3. Giữ nguyên input khi chuyển cuộc hội thoại
- Nếu đang soạn tin nhắn ở cuộc hội thoại A
- Chuyển sang cuộc hội thoại B
- Quay lại cuộc hội thoại A, nội dung đang soạn vẫn còn

### 4. Tránh race condition
- Khi gửi tin nhắn, lưu `conversationId` vào biến local
- Response luôn được thêm vào đúng cuộc hội thoại, dù user có chuyển đi chỗ khác

## Testing

### Test case 1: Chuyển cuộc hội thoại khi đang gửi tin nhắn
1. Mở cuộc hội thoại A
2. Gửi tin nhắn
3. Ngay lập tức chuyển sang cuộc hội thoại B
4. **Kết quả mong đợi:**
   - Cuộc hội thoại B không hiển thị loading
   - Khi response trả về, tin nhắn xuất hiện ở cuộc hội thoại A
   - Cuộc hội thoại B không bị ảnh hưởng

### Test case 2: Gửi tin nhắn đồng thời nhiều cuộc hội thoại
1. Mở cuộc hội thoại A, gửi tin nhắn
2. Chuyển sang cuộc hội thoại B, gửi tin nhắn
3. **Kết quả mong đợi:**
   - Cả hai cuộc hội thoại đều hiển thị loading
   - Response của mỗi cuộc hội thoại xuất hiện đúng chỗ

### Test case 3: Giữ nguyên input khi chuyển cuộc hội thoại
1. Mở cuộc hội thoại A, gõ một nửa tin nhắn (không gửi)
2. Chuyển sang cuộc hội thoại B
3. Quay lại cuộc hội thoại A
4. **Kết quả mong đợi:**
   - Nội dung đang soạn ở cuộc hội thoại A vẫn còn

## Cấu trúc dữ liệu

```typescript
// Ví dụ conversationStates Map
{
  123: {
    messages: [...],
    inputValue: "Hello",
    isLoading: false
  },
  456: {
    messages: [...],
    inputValue: "",
    isLoading: true  // Đang gửi tin nhắn
  },
  'new': {
    messages: [],
    inputValue: "Starting new chat",
    isLoading: false
  }
}
```

## Lưu ý khi phát triển

1. **Luôn sử dụng `getCurrentState()` và `updateCurrentState()`** thay vì truy cập trực tiếp vào Map
2. **Lưu `conversationId` vào biến local** trong các async function để tránh race condition
3. **Khởi tạo state** khi tạo hoặc chọn cuộc hội thoại mới
4. **Xóa state** khi xóa cuộc hội thoại để tránh memory leak
5. **Sử dụng key `'new'`** cho cuộc hội thoại chưa được tạo trên server
