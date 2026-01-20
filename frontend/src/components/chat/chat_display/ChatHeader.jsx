export default function ChatHeader({exportConversation, clearConversation, newSession, sessionId}) {
    return (
        <header className="bg-white shadow p-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-emerald-400 flex items-center justify-center text-white font-bold">
                CP
            </div>
            <div>
                <h1 className="text-lg font-semibold">Chinese Practice — Chat</h1>
                <p className="text-xs text-slate-500">
                Session: <span className="font-mono">{sessionId.slice(0, 8)}</span>
                </p>
            </div>
            </div>

            <div className="flex gap-2">
            <button onClick={exportConversation} className="px-3 py-1 rounded-md border text-sm hover:bg-slate-100">
                Export
            </button>
            <button onClick={clearConversation} className="px-3 py-1 rounded-md border text-sm hover:bg-slate-100">
                Clear
            </button>
            <button onClick={newSession} className="px-3 py-1 rounded-md bg-indigo-600 text-white text-sm hover:opacity-90">
                New Session
            </button>
            </div>
        </header>
    );
}