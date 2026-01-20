import ChatMessage from "./ChatMessage.jsx";

export default function ChatMessageList({ messages, listRef }) {
    return (
        <div ref={listRef} className="flex-1 overflow-auto mb-4 p-3 bg-white rounded-lg shadow-sm">
            {messages.length === 0 && <div className="text-center text-slate-400 mt-20">Start the conversation by typing or speaking.</div>}

            <div className="space-y-3">
              {messages.map((m) => (
                <ChatMessage key={m.id} message={m} />
              ))}
            </div>
          </div>
    );
}