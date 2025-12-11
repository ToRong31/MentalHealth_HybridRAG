# Conversation State Management

## Tổng quan

Hệ thống quản lý state cho các cuộc hội thoại được thiết kế theo hướng per-conversation state để đảm bảo:

Mỗi cuộc hội thoại hoạt động độc lập (messages, input, loading…)

Người dùng chuyển qua lại giữa các cuộc hội thoại trong khi request đang chạy không làm UI hiển thị sai

Response luôn được gắn đúng vào cuộc hội thoại đã gửi (tránh race condition)

Hỗ trợ gửi nhiều request đồng thời (giữa các cuộc hội thoại, và trong cùng một cuộc hội thoại nếu cần)

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

Mỗi cuộc hội thoại có state riêng, lưu trong Map theo key là conversationId hoặc 'new' (draft chat chưa có id).
```typescript
interface ConversationState {
  messages: Message[];
  inputValue: string;

  /**
   * Thay vì boolean, dùng pendingCount để:
   * - Hỗ trợ nhiều request trong cùng 1 conversation
   * - Không bị "response 1 về trước" làm tắt loading khi response 2 chưa về
   */
  pendingCount: number;
}

type ConversationKey = number | "new";

const DEFAULT_STATE: ConversationState = {
  messages: [],
  inputValue: "",
  pendingCount: 0,
};

const [conversationStates, setConversationStates] =
  useState<Map<ConversationKey, ConversationState>>(new Map());

}

const [conversationStates, setConversationStates] = 
    useState<Map<number | 'new', ConversationState>>(new Map());
```

### 2. Key Management

- **Cuộc hội thoại đã tồn tại**: Sử dụng `conversationId` làm key
- **Cuộc hội thoại mới**: Sử dụng string `new` làm key tạm thời
- Khi cuộc hội thoại mới được tạo, state được chuyển từ key `'new'` sang `conversationId` thực

### 3. Helper Functions (React-safe, không mutate Map)

#### `getStateByKey()`
Lấy state của cuộc hội thoại hiện tại:
```typescript
const getStateByKey = (key: ConversationKey): ConversationState => {
  return conversationStates.get(key) ?? DEFAULT_STATE;
};
```
getStateByKey chỉ nên dùng để đọc trong render. Với async flow, luôn update bằng functional setConversationStates(prev => ...).

#### `upsertStateByKey()`
Cập nhật state theo key mà không mutate Map cũ và tránh stale closure.
```typescript
const upsertStateByKey = (
  key: ConversationKey,
  updates: Partial<ConversationState>
) => {
  setConversationStates((prev) => {
    const prevState = prev.get(key) ?? DEFAULT_STATE;
    const next = new Map(prev);
    next.set(key, { ...prevState, ...updates });
    return next;
  });
};
```

#### `updateStateByKeyWithReducer()`   
Dùng khi update cần dựa trên state hiện tại (append message, merge…).
```typescript
const updateStateByKey = (
  key: ConversationKey,
  reducer: (state: ConversationState) => ConversationState
) => {
  setConversationStates((prev) => {
    const prevState = prev.get(key) ?? DEFAULT_STATE;
    const next = new Map(prev);
    next.set(key, reducer(prevState));
    return next;
  });
};
```

## Luồng hoạt động

### Khi chọn cuộc hội thoại

Mục tiêu:
1. Nếu chưa có state → khởi tạo bằng messages từ server
2. Nếu đã có state → merge/replace có kiểm soát để tránh ghi đè message local pending
Khuyến nghị: Nếu đang pending request trong conversation đó, không overwrite thô toàn bộ messages.

```typescript
const initOrSyncConversationFromServer = (
  conversationId: number,
  serverMessages: Message[]
) => {
  updateStateByKey(conversationId, (state) => {
    // Nếu không pending gì, có thể replace thẳng
    if (state.pendingCount === 0) {
      return { ...state, messages: serverMessages };
    }

    // Nếu đang pending: merge để không mất message local
    // (Tuỳ hệ thống id, có thể merge theo message.id)
    const localOnly = state.messages.filter((m) => m.source === "local");
    return { ...state, messages: [...serverMessages, ...localOnly] };
  });
};

```

### Khi gửi tin nhắn

1. Xác định key conversation tại thời điểm gửi (không phụ thuộc currentConversation sau này)
2. Optimistic update (append user message, clear input, tăng pendingCount)
3. Gửi request
4. Khi response về: giảm pendingCount, append assistant message theo key đã capture

```typescript
const handleSendMessage = async () => {
  const key: ConversationKey = currentConversation?.id ?? "new";
  const requestId = crypto.randomUUID();

  // Lấy input tại thời điểm gửi (từ state theo key)
  const input = (conversationStates.get(key) ?? DEFAULT_STATE).inputValue.trim();
  if (!input) return;

  // Optimistic update
  updateStateByKey(key, (state) => ({
    ...state,
    inputValue: "",
    pendingCount: state.pendingCount + 1,
    messages: [
      ...state.messages,
      {
        id: requestId, // client id
        role: "user",
        content: input,
        pending: true,
        source: "local",
      },
    ],
  }));

  try {
    const resp = await apiSendMessage({
      conversationId: key === "new" ? undefined : key,
      content: input,
      requestId,
    });

    // Nếu đây là new chat và server trả về conversationId thật → migrate
    if (key === "new" && resp.conversationId) {
      migrateNewToConversationId(resp.conversationId);
    }

    const finalKey: ConversationKey =
      key === "new" && resp.conversationId ? resp.conversationId : key;

    // Apply response vào đúng conversation
    updateStateByKey(finalKey, (state) => ({
      ...state,
      pendingCount: Math.max(0, state.pendingCount - 1),
      messages: [
        ...state.messages.map((m) =>
          m.id === requestId ? { ...m, pending: false, source: "server" } : m
        ),
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: resp.assistantText,
          source: "server",
        },
      ],
    }));
  } catch (err) {
    // Fail: giảm pendingCount và đánh dấu message lỗi
    updateStateByKey(key, (state) => ({
      ...state,
      pendingCount: Math.max(0, state.pendingCount - 1),
      messages: state.messages.map((m) =>
        m.id === requestId ? { ...m, pending: false, error: true } : m
      ),
    }));
  }
};
```

### Migrate state từ 'new' sang conversationId
Migrate phải atomic và không mutate Map cũ:
```typescript
const migrateNewToConversationId = (conversationId: number) => {
  setConversationStates((prev) => {
    const next = new Map(prev);
    const draft = next.get("new");
    if (!draft) return prev;

    next.set(conversationId, draft);
    next.delete("new");
    return next;
  });
};
```

### Khi xóa cuộc hội thoại
```typescript
const deleteConversationState = (conversationId: number) => {
  setConversationStates((prev) => {
    const next = new Map(prev);
    next.delete(conversationId);
    return next;
  });
};
```
Nếu đang xem cuộc hội thoại bị xoá: clear currentConversation ở tầng routing/UI.

## Lợi ích

### 1. Độc lập giữa các cuộc hội thoại
- Mỗi conversation có messages/input/pendingCount riêng
- Loading không “dính” qua conversation khác

### 2. Hỗ trợ gửi tin nhắn đồng thời
- Có thể gửi tin nhắn ở nhiều cuộc hội thoại cùng lúc
- Mỗi conversation hiển thị loading đúng theo pendingCount

### 3. Giữ nguyên input khi chuyển cuộc hội thoại
- Nếu đang soạn tin nhắn ở cuộc hội thoại A
- Chuyển sang cuộc hội thoại B
- Quay lại cuộc hội thoại A, nội dung đang soạn vẫn còn

### 4. Tránh race condition
Khi gửi, capture key và requestId

Response update dựa trên key/requestId đã capture, không phụ thuộc UI hiện tại

## Testing

### Test case 1: Chuyển cuộc hội thoại khi đang gửi tin nhắn
1. Mở cuộc hội thoại A
2. Gửi tin nhắn
3. Ngay lập tức chuyển sang cuộc hội thoại B
4. **Kết quả mong đợi:**
   - Cuộc hội thoại B không hiển thị loading
   - Khi response trả về, tin nhắn xuất hiện ở cuộc hội thoại A
   - Cuộc hội thoại B không bị ảnh hưởng
   - A pendingCount về 0 khi xong

### Test case 2: Gửi tin nhắn đồng thời nhiều cuộc hội thoại
1. Mở cuộc hội thoại A, gửi tin nhắn
2. Chuyển sang cuộc hội thoại B, gửi tin nhắn
A gửi → pendingCount(A)=1

B gửi → pendingCount(B)=1
3. **Kết quả mong đợi:**
   - cả hai loading độc lập
   - Response của mỗi cuộc hội thoại xuất hiện đúng chỗ, pending count giảm đúng

### Test case 3: Giữ nguyên input khi chuyển cuộc hội thoại
1. Mở cuộc hội thoại A, gõ một nửa tin nhắn (không gửi)
2. Chuyển sang cuộc hội thoại B
3. Quay lại cuộc hội thoại A
4. **Kết quả mong đợi:**
   - Nội dung đang soạn ở cuộc hội thoại A vẫn còn

### Test case 4: Sync server messages khi đang pending

1. A đang pending
2. user re-open conversation / app refetch messages
3. **Expected**
    - không mất local pending message
    - merge logic giữ message local ở cuối (hoặc reconcile theo id)

## Cấu trúc dữ liệu ví dụ

```typescript
// Ví dụ conversationStates Map
{
  123: {
    messages: [...],
    inputValue: "Hello",
    pendingCount: 0
  },
  456: {
    messages: [...],
    inputValue: "",
    pendingCount: 1
  },
  "new": {
    messages: [],
    inputValue: "Starting new chat",
    pendingCount: 0
  }
}

```

## Lưu ý khi phát triển

Không mutate Map trong React state (set, delete trên object cũ)

Luôn dùng setConversationStates(prev => new Map(prev) ...)

Tránh stale closure trong async

Không đọc conversationStates sau await để quyết định update

Luôn update bằng functional form (prev => ...) / reducer

Không dùng isLoading: boolean nếu có thể có nhiều request

Dùng pendingCount hoặc pendingRequestIds

Khi sync từ server, tránh overwrite thô messages

Merge/reconcile để không mất local pending/optimistic

Migrate 'new' → conversationId phải atomic

Dùng functional setConversationStates
