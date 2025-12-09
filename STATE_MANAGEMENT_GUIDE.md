# State Management Test Guide

## Overview

The application has been refactored with a robust per-conversation state management system that handles all the edge cases mentioned in your test scenarios. Here's how it works:

## Architecture

### Key Components

1. **Per-Conversation State Storage** (`conversationStatesRef`)
   - Each conversation (including "new") has its own isolated state
   - Stores: messages, input draft, pending count, and server messages
   - Uses conversation ID as key (or "new" for new conversations)

2. **Pending Message Tracking**
   - Each sent message gets a unique `tempId`
   - Pending messages have `isPending: true` flag
   - Visual indicator (⏳) shows pending state
   - Pending messages are reconciled when server responds

3. **Race Condition Prevention**
   - Each request tracked with unique identifier
   - Responses matched to correct conversation
   - Outdated responses safely ignored

4. **Input Draft Persistence**
   - Input text saved per conversation
   - Survives conversation switching
   - Cleared only on send

## Test Cases

### ✅ Test Case 1: Switch Conversation While Sending

**Steps:**
1. Open conversation A
2. Type and send a message
3. Immediately switch to conversation B

**Expected Results:**
- ✅ Conversation A shows pending indicator (⏳) on user message
- ✅ Conversation B does NOT show loading indicator
- ✅ When response arrives, it appears in conversation A only
- ✅ Conversation B remains unchanged
- ✅ Pending count in A goes to 0 after response

**Implementation:**
```typescript
// Home.tsx lines ~160-230
// Each conversation tracks its own pendingCount
// Response is routed back to original conversation via tempId mapping
```

### ✅ Test Case 2: Send Messages to Multiple Conversations

**Steps:**
1. Open conversation A, send message (pendingCount(A) = 1)
2. Switch to conversation B, send message (pendingCount(B) = 1)

**Expected Results:**
- ✅ Both conversations show their own loading states
- ✅ Each response appears in correct conversation
- ✅ Pending counts decrease independently
- ✅ No cross-contamination of messages

**Implementation:**
```typescript
// Per-conversation state ensures isolation
conversationStatesRef.current.get(conversationKey).pendingCount
```

### ✅ Test Case 3: Input Draft Persistence

**Steps:**
1. Open conversation A, type half a message (don't send)
2. Switch to conversation B
3. Switch back to conversation A

**Expected Results:**
- ✅ Draft text in conversation A is preserved
- ✅ Draft text in conversation B is independent
- ✅ No text lost during navigation

**Implementation:**
```typescript
// Home.tsx lines ~274-278
const handleInputChange = (value: string) => {
  const convKey = getConversationKey(currentConversationId);
  updateConversationState(convKey, { inputDraft: value });
};
```

### ✅ Test Case 4: Server Message Sync with Pending Messages

**Steps:**
1. Conversation A has pending message
2. User refreshes or re-opens conversation
3. App fetches messages from server

**Expected Results:**
- ✅ Pending messages not lost
- ✅ Server messages merged correctly
- ✅ No duplicate messages
- ✅ Pending messages appear after server messages

**Implementation:**
```typescript
// Home.tsx lines ~66-77
const mergeMessages = (serverMessages, pendingMessages) => {
  const serverMap = new Map(serverMessages.map(m => [m.id, m]));
  const merged = [...serverMessages];
  
  pendingMessages.forEach(pm => {
    if (pm.isPending && !serverMap.has(pm.id)) {
      merged.push(pm);
    }
  });
  
  return merged.sort((a, b) => 
    new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  );
};
```

## Visual Indicators

### Pending Message
- Opacity reduced to 70%
- Hourglass emoji (⏳) with pulsing animation
- Tooltip: "Đang gửi..."

### CSS Classes
```css
.message-pending .message-content {
  opacity: 0.7;
}

.pending-indicator {
  animation: pulse 1.5s ease-in-out infinite;
}
```

## Data Flow

### Sending a Message

1. **User types and sends**
   ```
   User Input → handleSendMessage()
   ```

2. **Create pending message**
   ```
   tempId = "temp-{timestamp}-{random}"
   isPending = true
   ```

3. **Update local state**
   ```
   conversationState.messages.push(pendingMessage)
   conversationState.pendingCount++
   conversationState.inputDraft = ""
   ```

4. **Send to API**
   ```
   sendMessage() → Backend
   ```

5. **Handle response**
   ```
   - Find target conversation by tempId
   - Remove pending message
   - Add real messages from server
   - Merge with any other pending messages
   - Decrement pendingCount
   ```

### Switching Conversations

1. **User clicks conversation**
   ```
   handleSelectConversation(id)
   ```

2. **Load state**
   ```
   - Get conversation state from ref
   - If empty, fetch from server
   - Merge server messages with pending
   - Update currentConversationId
   ```

3. **Render**
   ```
   - ChatInterface receives conversation-specific state
   - Input shows saved draft
   - Messages show pending indicators
   ```

## Error Handling

### Network Error During Send

1. Pending message remains visible
2. Error message added to conversation
3. Pending count decremented
4. User can retry sending

### Race Condition (Response After Switch)

1. Response matched to original conversation via tempId
2. Message added to correct conversation's state
3. Current view unaffected if different conversation
4. Pending count updated correctly

## Benefits vs Previous Implementation

| Feature | Old | New |
|---------|-----|-----|
| Per-conversation loading | ❌ Global | ✅ Isolated |
| Input persistence | ❌ Lost on switch | ✅ Saved per conversation |
| Pending message tracking | ❌ None | ✅ Full reconciliation |
| Race condition handling | ⚠️ Partial | ✅ Complete |
| Multi-conversation sends | ❌ Conflicts | ✅ Independent |
| Message deduplication | ❌ None | ✅ Automatic |

## Testing Instructions

### Manual Testing

1. **Open the application**
   ```
   Frontend: http://localhost:5173
   Backend: http://localhost:8000
   ```

2. **Test concurrent sends**
   - Open conversation A, send message
   - Quickly switch to conversation B, send message
   - Observe both have pending indicators
   - Verify responses appear in correct conversations

3. **Test input persistence**
   - Type in conversation A (don't send)
   - Switch to conversation B
   - Switch back to A
   - Verify text is still there

4. **Test pending during switch**
   - Send message in conversation A
   - Immediately switch to conversation B
   - Verify B doesn't show loading
   - Switch back to A
   - Verify response appeared correctly

### Developer Console

Monitor state in browser console:
```javascript
// The conversationStatesRef is visible in React DevTools
// Look for Home component
// Inspect conversationStatesRef.current
```

## Comparison with Popular Chatbots

### ChatGPT
- ✅ Per-thread input persistence
- ✅ Pending message indicators
- ✅ Independent thread loading

### Claude (Anthropic)
- ✅ Draft saving per conversation
- ✅ Optimistic UI updates
- ✅ Message reconciliation

### Our Implementation
- ✅ All of the above
- ✅ Plus explicit pending count tracking
- ✅ Visual pending indicators with animation

## Future Enhancements

1. **Local Storage Persistence**
   - Save draft inputs to localStorage
   - Survive browser refresh

2. **Offline Support**
   - Queue messages when offline
   - Send when connection restored

3. **Edit & Retry**
   - Edit pending messages
   - Retry failed sends

4. **Batch Operations**
   - Send to multiple conversations
   - Bulk message management

## Troubleshooting

### Messages appearing in wrong conversation
- Check `pendingRequestsRef` mapping
- Verify `tempId` uniqueness
- Inspect `conversationKey` calculation

### Lost draft text
- Check `getConversationState()` logic
- Verify `updateConversationState()` calls
- Inspect `conversationStatesRef.current` Map

### Race condition issues
- Check request tracking in `pendingRequestsRef`
- Verify `tempId` matching in response handler
- Look for premature cleanup

## Code References

- `frontend/src/pages/Home.tsx` - Main state management
- `frontend/src/components/ChatInterface.tsx` - UI rendering
- `frontend/src/types.ts` - Type definitions
- `frontend/src/assets/styles/App.css` - Pending message styles
