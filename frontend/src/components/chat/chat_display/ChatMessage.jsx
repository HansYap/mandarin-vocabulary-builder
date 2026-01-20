export default function ChatMessage({ message }) {
    return (
        <>
            <div 
                key={message.id} 
                className={`p-3 rounded-lg max-w-[80%] transition-all duration-300 ${
                message.role === "user" 
                    ? "ml-auto bg-indigo-50 border-transparent" 
                    : "mr-auto bg-slate-100 border-transparent"
                } border`}
            >
                <div className="text-sm whitespace-pre-wrap">
                {message.isPlaceholder ? (
                    <div className="flex items-center gap-2 py-1">
                    <span className="text-slate-400 italic font-medium">Thinking</span>
                    <div className="flex">
                        <span className="dot"></span>
                        <span className="dot"></span>
                        <span className="dot"></span>
                    </div>
                    </div>
                ) : (
                    message.text
                )}
                </div>
                <div className="text-[11px] text-slate-400 mt-1 text-right">
                {new Date(message.ts).toLocaleString()}
                </div>
            </div>

            <style jsx>{`
            @keyframes bounce {
            0%, 80%, 100% { transform: translateY(0); }
            40% { transform: translateY(-5px); }
            }

            .dot {
            display: inline-block;
            width: 6px;
            height: 6px;
            margin: 0 2px;
            background-color: #94a3b8; /* slate-400 */
            border-radius: 50%;
            animation: bounce 1.4s infinite ease-in-out both;
            }

            .dot:nth-child(1) { animation-delay: -0.32s; }
            .dot:nth-child(2) { animation-delay: -0.16s; }
        `}</style>
      </>
    );
}