import ChatMessageList from "./ChatMessageList";
import ChatInputArea from "../chat_controls/ChatInputArea";
import ErrorBanner from "../../ui/ErrorBanner";
import NewSessionBanner from "../../ui/NewSessionBanner";
import LiveTranscriptBanner from "../../ui/LiveTranscriptBanner";
import TranscriptEditor from "../chat_controls/TranscriptEditor";  

export default function ChatColumn({
    messages,
    listRef,
    error,
    sessionEnded,
    liveTranscript,
    pendingTranscript,
    handleCancelEdit,
    editTextareaRef,
    loading,
    handleSendEdited,
    editableText,
    setEditableText,
    input,
    setInput,
    handleKeyDown,
    isRecording,
    sendMessage,
    startRecording,
    stopRecording,
    endSession,
    endingSession,
    autoSubmit,
    setAutoSubmit
}) {
    return (
        <div className="flex-1 flex flex-col" style={{ maxHeight: 'calc(100vh - 8rem)' }}>
                  <ChatMessageList messages={messages} listRef={listRef} />
        
                  <div className="bg-white p-3 rounded-lg shadow flex flex-col gap-2">
                    <ErrorBanner error={error} />
        
                    <NewSessionBanner sessionEnded={sessionEnded} />
        
                    <LiveTranscriptBanner liveTranscript={liveTranscript} />
        
                    <TranscriptEditor 
                      pendingTranscript={pendingTranscript}
                      handleCancelEdit={handleCancelEdit}
                      editTextareaRef={editTextareaRef}
                      loading={loading}
                      handleSendEdited={handleSendEdited}
                      editableText={editableText}
                      setEditableText={setEditableText}
                    />
        
                    <ChatInputArea 
                      input={input}
                      setInput={setInput}
                      handleKeyDown={handleKeyDown}
                      isRecording={isRecording}
                      pendingTranscript={pendingTranscript}
                      loading={loading}
                      endingSession={endingSession}
                      sendMessage={sendMessage}
                      startRecording={startRecording}
                      stopRecording={stopRecording}
                      endSession={endSession}
                      messages={messages}
                      autoSubmit={autoSubmit}
                      setAutoSubmit={setAutoSubmit}
                    /> 
                  </div>
                </div>
    );
}