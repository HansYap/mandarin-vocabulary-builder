import Spinner from "../../ui/Spinner.jsx";

export default function ChatButtonBar({ 
    sendMessage,
    loading,
    isRecording,
    startRecording,
    stopRecording,
    pendingTranscript,
    endingSession,
    endSession,
    messages,
    autoSubmit,
    setAutoSubmit
 }) {
    return (
        <div className="flex items-center justify-between gap-3">
            <div className="flex gap-2 items-center flex-wrap">
            <button
                onClick={sendMessage}
                disabled={loading || isRecording || pendingTranscript !== null || endingSession}
                className={`
                px-4 py-2 rounded-md font-medium
                flex items-center justify-center
                transition-colors duration-200
                ${
                    loading
                    ? "bg-gray-300 text-gray-600 cursor-not-allowed"
                    : "bg-emerald-500 text-white hover:bg-emerald-600"
                }
                disabled:opacity-60 disabled:cursor-not-allowed
                `}
            >
                <span className="relative inline-flex items-center justify-center">
                {/* Text (defines width) */}
                <span className={loading ? "invisible" : "visible"}>
                    发送 / Send Message
                </span>

                {/* Spinner (overlayed) */}
                <span
                    className={`
                    absolute inset-0 flex items-center justify-center
                    ${loading ? "opacity-100" : "opacity-0"}
                    `}
                >
                    <Spinner />
                </span>
                </span>
            </button>

            <button 
                onClick={isRecording ? stopRecording : startRecording} 
                disabled={pendingTranscript !== null || loading || endingSession}
                className={`px-3 py-2 rounded-md text-sm font-medium ${
                isRecording 
                    ? "bg-red-500 text-white animate-pulse" 
                    : "bg-blue-500 text-white hover:bg-blue-600"
                }disabled:opacity-60 disabled:cursor-not-allowed`}>
                {isRecording ? "⏹ Stop Speaking" : "🎤 Start Speaking"}
            </button>

            <button
                onClick={() => setAutoSubmit(!autoSubmit)}
                disabled={isRecording || loading || endingSession}
                className={`px-3 py-2 rounded-md text-sm font-medium border-2 transition-colors ${
                autoSubmit
                    ? "bg-green-500 text-white border-green-600"
                    : "bg-white text-slate-700 border-slate-300"
                } disabled:opacity-60 disabled:cursor-not-allowed`}
            >
                {autoSubmit ? "⚡ Auto" : "✋ Manual"}
            </button>

            <button 
                onClick={endSession} 
                disabled={endingSession || loading || isRecording}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-all ${
                endingSession ? "bg-orange-400 text-white opacity-60" : "bg-orange-400 text-white hover:bg-orange-500 disabled:opacity-60 disabled:cursor-not-allowed"
                }`}
            >
                <span className="inline-flex items-center justify-center gap-2">
                {endingSession ? (
                    <>
                    <Spinner />
                    Generating feedback
                    </>
                ) : (
                    "End Session"
                )}
                </span>
            </button>
            </div>

            <div className="text-sm text-slate-500">
            <div>Messages: {messages.length}</div>
            </div>
        </div>
    );
}