import { useEffect, useRef, useState } from "react";
import { v4 as uuidv4 } from "uuid";
import { io } from "socket.io-client";
import { useDictionary } from './hooks/useDictionary';
import DictionaryContainer from './components/dictionary/DictionaryContainer';
import { useSession } from "./hooks/useSession";
import FeedbackSidebar from "./components/feedback/FeedbackSidebar";
import { useChat } from "./hooks/useChat";
import ChatHeader from "./components/chat/chat_display/ChatHeader";
import ChatColumn from "./components/chat/chat_display/ChatColumn";


const SOCKET_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:5000";
const cleanSocketUrl = SOCKET_URL.endsWith('/') ? SOCKET_URL.slice(0, -1) : SOCKET_URL;

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [error, setError] = useState(null);
  const [autoSubmit, setAutoSubmit] = useState(false);
  const [pendingTranscript, setPendingTranscript] = useState(null);
  const [editableText, setEditableText] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState("");
  
  const audioRef = useRef(null);
  const socketRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);
  const editTextareaRef = useRef(null);

  const {
    dictionaryEntry,
    dictionaryLoading,
    popoverPosition,
    isMobile,
    lookupDictionary,
    closeDictionary,
  } = useDictionary();

  const {
    feedback,
    sessionId,
    endingSession,
    sessionEnded,
    setFeedback,
    endSession,
    newSession,
    exportFeedback,
  } = useSession({
    audioRef,
    setMessages,
    setLiveTranscript,
    setPendingTranscript,
    setEditableText,
    closeDictionary,
    setError,
  });

  const {
    listRef,
    loading,
    sendToChat,
    clearConversation,
    exportConversation,
  } = useChat({ 
    messages,
    setMessages,
    sessionId, 
    setError,
    audioRef,
  });


  

  useEffect(() => {
    const socket = io(cleanSocketUrl, { 
      transports: ["websocket"],
      reconnection: true
    });
    socketRef.current = socket;

    socket.on("connect", () => {
      console.log("Socket connected:", socket.id);
    });

    socket.on("partial_transcript", (data) => {
      console.log("Partial transcript:", data);
      const text = data?.text || "";
      setLiveTranscript(text);
    });

    socket.on("final_transcript", async (data) => {
      console.log("Final transcript (legacy):", data);
      const text = (data && data.text) || "";
      setLiveTranscript("");
      if (!text) return;
      await sendToChat(text);
    });

    socket.on("transcript_ready", async (data) => {
      console.log("Transcript ready:", data);
      const text = (data && data.text) || "";
      const shouldAutoSubmit = data.auto_submit || autoSubmit;
      
      setLiveTranscript("");
      if (!text) return;

      if (shouldAutoSubmit) {
        console.log("🚀 Auto-submitting transcript");
        await sendToChat(text, false, null);
      } else {
        console.log("✋ Manual mode: Showing transcript for editing");
        setPendingTranscript(text);
        setEditableText(text);
      }
    });

    socket.on("transcript_confirmed", (data) => {
      console.log("Transcript confirmed:", data);
    });

    socket.on("session_ready", (d) => {
      console.log("Session ready:", d);
    });

    socket.on("connect_error", (err) => {
      console.error("Socket connect error:", err);
      setError("Socket connection failed: " + err.message);
    });

    socket.on("disconnect", () => {
      console.log("Socket disconnected");
    });

    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
      }
      if (audioRef.current) {
        audioRef.current.pause();
      }
    };
  }, [sessionId, autoSubmit]);

  useEffect(() => {
    if (pendingTranscript && editTextareaRef.current) {
      editTextareaRef.current.focus();
    }
  }, [pendingTranscript]);

  async function startRecording() {
    setError(null);
    setLiveTranscript("");
    setPendingTranscript(null);

    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setError("浏览器不支持麦克风访问");
      return;
    }

    try {
      console.log("Starting recording...");
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          channelCount: 1,
          sampleRate: 16000
        }
      });
      
      streamRef.current = stream;

      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : "audio/wav";
      
      console.log("Using MIME type:", mimeType);

      const mediaRecorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = mediaRecorder;

      console.log("Emitting start_speak");
      socketRef.current.emit("start_speak", { session_id: sessionId });

      mediaRecorder.ondataavailable = async (e) => {
        if (!e.data || e.data.size === 0) return;
        
        console.log(`Chunk size: ${e.data.size} bytes`);

        try {
          const arrayBuffer = await e.data.arrayBuffer();
          const uint8 = new Uint8Array(arrayBuffer);
          
          socketRef.current.emit("audio_chunk", {
            session_id: sessionId,
            chunk: Array.from(uint8),
          });
        } catch (err) {
          console.error("Chunk send error:", err);
        }
      };

      mediaRecorder.onstart = () => {
        console.log("Recording started");
        setIsRecording(true);
      };
      
      mediaRecorder.onstop = () => {
        console.log("⏹Recording stopped");
        setIsRecording(false);
        
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(track => track.stop());
        }
      };

      mediaRecorder.start(1000);
      
    } catch (e) {
      console.error("startRecording error:", e);
      setError("无法开启麦克风: (Please enable microphone usage for browser if not enabled) " + (e.message || e));
    }
  }

  function stopRecording() {
    try {
      console.log("⏹Stopping recording...");
      
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
        mediaRecorderRef.current.stop();
      }
      
      console.log("Emitting end_speak with auto_submit:", autoSubmit);
      socketRef.current.emit("end_speak", { 
        session_id: sessionId,
        auto_submit: autoSubmit
      });
      
    } catch (e) {
      console.error("stopRecording error:", e);
      setError("停止录音失败");
    }
  }

  async function handleSendEdited() {
    const originalText = pendingTranscript;
    const finalText = editableText.trim();
    
    if (!finalText) {
      setError("Cannot send empty message");
      return;
    }

    const isEdited = finalText !== originalText;
    
    socketRef.current.emit("confirm_transcript", {
      session_id: sessionId,
      text: finalText
    });

    setPendingTranscript(null);
    setEditableText("");

    await sendToChat(finalText, isEdited, originalText);
  }

  function handleCancelEdit() {
    setPendingTranscript(null);
    setEditableText("");
  }

  async function sendMessage() {
    const text = input.trim();
    if (!text) return;

    setError(null);
    setInput("");        

    await sendToChat(text); 
  }

  async function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      await sendMessage();
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <ChatHeader 
        exportConversation={exportConversation}
        clearConversation={clearConversation}
        newSession={newSession}
        sessionId={sessionId}
      />

      <main className="flex-1 p-4 max-w-5xl mx-auto w-full flex gap-4">
        {/* Chat Column */}
        <ChatColumn
          messages={messages}
          listRef={listRef}
          error={error}
          sessionEnded={sessionEnded}
          liveTranscript={liveTranscript}
          pendingTranscript={pendingTranscript}
          handleCancelEdit={handleCancelEdit}
          editTextareaRef={editTextareaRef}
          loading={loading}
          handleSendEdited={handleSendEdited}
          editableText={editableText}
          setEditableText={setEditableText}
          input={input}
          setInput={setInput}
          handleKeyDown={handleKeyDown}
          isRecording={isRecording}
          sendMessage={sendMessage}
          startRecording={startRecording}
          stopRecording={stopRecording}
          endSession={endSession}
          endingSession={endingSession}
          autoSubmit={autoSubmit}
          setAutoSubmit={setAutoSubmit}
        />

        {/* Feedback Sidebar */}
        <FeedbackSidebar 
          feedbackItems={feedback} 
          lookupDictionary={lookupDictionary} 
          onExport={exportFeedback}
          onClose={() => setFeedback(null)}
        />
      </main>
      
      {/* Desktop Popover & Mobile Bottom Sheet */}
      <DictionaryContainer
        entry={dictionaryEntry}
        loading={dictionaryLoading}
        position={popoverPosition}
        isMobile={isMobile}
        onClose={closeDictionary}
      />
    </div>
  );
}