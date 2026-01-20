import ChatButtonBar from "./ChatButtonBar";

export default function ChatInputArea({ 
    input, 
    handleKeyDown, 
    isRecording, 
    pendingTranscript, 
    loading, 
    endingSession,
    sendMessage,
    startRecording,
    stopRecording,
    endSession,
    messages,
    autoSubmit,
    setAutoSubmit,
    setInput,
}) {
    return (
        <>
            <textarea 
                value={input} 
                onChange={(e) => setInput(e.target.value)} 
                onKeyDown={handleKeyDown} 
                placeholder="输入中文或英文（按 Enter 发送，Shift+Enter 换行）" 
                rows={3} 
                className="w-full p-2 rounded border resize-none focus:outline-none focus:ring disabled:bg-slate-100 disabled:opacity-60 disabled:cursor-not-allowed" 
                disabled={isRecording || pendingTranscript !== null || loading || endingSession}
            />
            <ChatButtonBar 
                sendMessage={sendMessage}
                loading={loading}
                isRecording={isRecording}
                startRecording={startRecording}
                stopRecording={stopRecording}
                pendingTranscript={pendingTranscript}
                endingSession={endingSession}
                endSession={endSession}
                messages={messages}
                autoSubmit={autoSubmit}
                setAutoSubmit={setAutoSubmit}
            />
        </>
    )
}