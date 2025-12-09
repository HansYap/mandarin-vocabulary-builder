import React, { useEffect, useRef, useState } from "react";
import { v4 as uuidv4 } from "uuid";
import { io } from "socket.io-client";

const SOCKET_URL = "http://127.0.0.1:5000";

export default function App() {
  const [sessionId, setSessionId] = useState(() => {
    try {
      const saved = localStorage.getItem("chat_session_id");
      return saved || uuidv4();
    } catch (e) {
      return uuidv4();
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem("chat_session_id", sessionId);
    } catch (e) {}
  }, [sessionId]);

  const [messages, setMessages] = useState(() => {
    try {
      const raw = localStorage.getItem("chat_messages_" + sessionId);
      return raw ? JSON.parse(raw) : [];
    } catch (e) {
      return [];
    }
  });
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [error, setError] = useState(null);
  const listRef = useRef(null);

  // NEW: Auto-submit toggle state
  const [autoSubmit, setAutoSubmit] = useState(() => {
    try {
      const saved = localStorage.getItem("auto_submit_mode");
      return saved === "true";
    } catch (e) {
      return false; // Default to manual mode
    }
  });

  // NEW: Pending transcript state for manual edit mode
  const [pendingTranscript, setPendingTranscript] = useState(null);
  const [editableText, setEditableText] = useState("");

  // Save auto-submit preference
  useEffect(() => {
    try {
      localStorage.setItem("auto_submit_mode", autoSubmit.toString());
    } catch (e) {}
  }, [autoSubmit]);

  // Audio ref for playing TTS
  const audioRef = useRef(null);

  // mic/socket refs
  const socketRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);
  const [isRecording, setIsRecording] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState("");

  useEffect(() => {
    try {
      localStorage.setItem("chat_messages_" + sessionId, JSON.stringify(messages));
    } catch (e) {}
  }, [messages, sessionId]);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages, loading]);

  // Function to play audio
  function playAudio(audioDataUrl) {
    if (!audioDataUrl) return;
    
    try {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.currentTime = 0;
      }
      
      audioRef.current = new Audio(audioDataUrl);
      audioRef.current.play().catch(err => {
        console.error("Audio playback error:", err);
        setError("Audio playback failed");
      });
    } catch (err) {
      console.error("Audio creation error:", err);
    }
  }

  // NEW: Function to send chat (used by both auto and manual modes)
  async function sendToChat(text, isEdited = false, originalText = null) {
    if (!text.trim()) {
      console.log("⚠️ Empty text, skipping chat");
      return;
    }

    // Show final user message
    const userMsg = {
      id: uuidv4(),
      role: "user",
      text,
      ts: new Date().toISOString(),
    };
    setMessages((m) => [...m, userMsg]);

    // Auto-send to /api/chat
    try {
      setLoading(true);
      console.log("📤 Sending to /api/chat:", text);
      
      const resp = await fetch("http://127.0.0.1:5000/api/chat/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          text, 
          session_id: sessionId,
          is_edited: isEdited,
          original_text: originalText
        }),
      });
      
      if (!resp.ok) {
        const txt = await resp.text();
        throw new Error(txt || resp.statusText);
      }
      
      const d = await resp.json();
      console.log("📥 Response from /api/chat:", d);
      
      const assistantMsg = {
        id: uuidv4(),
        role: "assistant",
        text: d.response || d.message || "（无回复）",
        ts: new Date().toISOString(),
      };
      setMessages((m) => [...m, assistantMsg]);
      
      // Play audio if available
      if (d.audio) {
        console.log("🔊 Playing TTS audio");
        playAudio(d.audio);
      }
    } catch (e) {
      console.error("❌ Chat error:", e);
      setError("无法联系后端: " + (e.message || e));
      const failMsg = {
        id: uuidv4(),
        role: "assistant",
        text: "抱歉，出了一点问题，稍后再试。",
        ts: new Date().toISOString(),
      };
      setMessages((m) => [...m, failMsg]);
    } finally {
      setLoading(false);
    }
  }

  // Initialize socket once
  useEffect(() => {
    const socket = io(SOCKET_URL, { 
      transports: ["websocket"],
      reconnection: true
    });
    socketRef.current = socket;

    socket.on("connect", () => {
      console.log("✅ Socket connected:", socket.id);
    });

    socket.on("partial_transcript", (data) => {
      console.log("📝 Partial transcript:", data);
      const text = data?.text || "";
      setLiveTranscript(text);
    });

    // OLD EVENT: Keep for backward compatibility
    socket.on("final_transcript", async (data) => {
      console.log("✅ Final transcript (legacy):", data);
      const text = (data && data.text) || "";
      
      setLiveTranscript("");
      
      if (!text) {
        console.log("⚠️ Empty final transcript");
        return;
      }

      // Legacy: Auto-send
      await sendToChat(text);
    });

    // NEW EVENT: Handle transcript_ready
    socket.on("transcript_ready", async (data) => {
      console.log("✅ Transcript ready:", data);
      const text = (data && data.text) || "";
      const shouldAutoSubmit = data.auto_submit || autoSubmit;
      
      setLiveTranscript("");
      
      if (!text) {
        console.log("⚠️ Empty transcript");
        return;
      }

      if (shouldAutoSubmit) {
        // Auto-submit mode: Send immediately
        console.log("🚀 Auto-submitting transcript");
        await sendToChat(text, false, null);
      } else {
        // Manual mode: Show for editing
        console.log("✋ Manual mode: Showing transcript for editing");
        setPendingTranscript(text);
        setEditableText(text);
        // Focus will be handled by useEffect below
      }
    });

    socket.on("transcript_confirmed", (data) => {
      console.log("✅ Transcript confirmed:", data);
    });

    socket.on("session_ready", (d) => {
      console.log("✅ Session ready:", d);
    });

    socket.on("connect_error", (err) => {
      console.error("❌ Socket connect error:", err);
      setError("Socket connection failed: " + err.message);
    });

    socket.on("disconnect", () => {
      console.log("🔌 Socket disconnected");
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

  // Auto-focus on editable text when pending transcript appears
  const editTextareaRef = useRef(null);
  useEffect(() => {
    if (pendingTranscript && editTextareaRef.current) {
      editTextareaRef.current.focus();
    }
  }, [pendingTranscript]);

  async function startRecording() {
    setError(null);
    setLiveTranscript("");
    setPendingTranscript(null); // Clear any pending transcript
    
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setError("浏览器不支持麦克风访问");
      return;
    }

    try {
      console.log("🎤 Starting recording...");
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
      
      console.log("📼 Using MIME type:", mimeType);

      const mediaRecorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = mediaRecorder;

      console.log("📤 Emitting start_speak");
      socketRef.current.emit("start_speak", { session_id: sessionId });

      mediaRecorder.ondataavailable = async (e) => {
        if (!e.data || e.data.size === 0) {
          console.log("⚠️ Empty data chunk");
          return;
        }
        
        console.log(`📦 Chunk size: ${e.data.size} bytes`);

        try {
          const arrayBuffer = await e.data.arrayBuffer();
          const uint8 = new Uint8Array(arrayBuffer);
          
          console.log(`📤 Sending chunk: ${uint8.length} bytes`);
          
          socketRef.current.emit("audio_chunk", {
            session_id: sessionId,
            chunk: Array.from(uint8),
          });
        } catch (err) {
          console.error("❌ Chunk send error:", err);
        }
      };

      mediaRecorder.onstart = () => {
        console.log("✅ Recording started");
        setIsRecording(true);
      };
      
      mediaRecorder.onstop = () => {
        console.log("⏹️ Recording stopped");
        setIsRecording(false);
        
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(track => track.stop());
        }
      };

      mediaRecorder.start(1000);
      
    } catch (e) {
      console.error("❌ startRecording error:", e);
      setError("无法开启麦克风: " + (e.message || e));
    }
  }

  function stopRecording() {
    try {
      console.log("⏹️ Stopping recording...");
      
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
        mediaRecorderRef.current.stop();
      }
      
      console.log("📤 Emitting end_speak with auto_submit:", autoSubmit);
      socketRef.current.emit("end_speak", { 
        session_id: sessionId,
        auto_submit: autoSubmit
      });
      
    } catch (e) {
      console.error("❌ stopRecording error:", e);
      setError("停止录音失败");
    }
  }

  // NEW: Handle sending edited transcript
  async function handleSendEdited() {
    const originalText = pendingTranscript;
    const finalText = editableText.trim();
    
    if (!finalText) {
      setError("Cannot send empty message");
      return;
    }

    const isEdited = finalText !== originalText;
    
    // Optional: Notify backend of confirmation
    socketRef.current.emit("confirm_transcript", {
      session_id: sessionId,
      text: finalText
    });

    // Clear pending state
    setPendingTranscript(null);
    setEditableText("");

    // Send to chat
    await sendToChat(finalText, isEdited, originalText);
  }

  // NEW: Cancel edited transcript
  function handleCancelEdit() {
    setPendingTranscript(null);
    setEditableText("");
  }

  async function sendMessage() {
    const text = input.trim();
    if (!text) return;
    setError(null);

    const userMsg = {
      id: uuidv4(),
      role: "user",
      text,
      ts: new Date().toISOString(),
    };

    setMessages((m) => [...m, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const resp = await fetch("http://127.0.0.1:5000/api/chat/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, session_id: sessionId }),
      });

      if (!resp.ok) {
        const txt = await resp.text();
        throw new Error(txt || resp.statusText);
      }

      const data = await resp.json();

      const assistantMsg = {
        id: uuidv4(),
        role: "assistant",
        text: data.response || data.message || "（无回复）",
        ts: new Date().toISOString(),
      };

      setMessages((m) => [...m, assistantMsg]);
      
      // Play audio if available
      if (data.audio) {
        console.log("🔊 Playing TTS audio");
        playAudio(data.audio);
      }
    } catch (e) {
      console.error("Send error", e);
      setError("无法联系后端: " + (e.message || e));
      const failMsg = {
        id: uuidv4(),
        role: "assistant",
        text: "抱歉，我好像遇到一点问题，你可以再说一次吗？",
        ts: new Date().toISOString(),
      };
      setMessages((m) => [...m, failMsg]);
    } finally {
      setLoading(false);
    }
  }

  async function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      await sendMessage();
    }
  }

  async function endSession() {
    setError(null);
    try {
      const resp = await fetch("http://127.0.0.1:5000/api/end-session/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId }),
      });

      if (!resp.ok) {
        const txt = await resp.text();
        throw new Error(txt || resp.statusText);
      }

      const data = await resp.json();
      setFeedback(data.feedback || data);
    } catch (e) {
      console.error("End session error", e);
      setError("结束会话失败: " + (e.message || e));
    }
  }

  function clearConversation() {
    setMessages([]);
    try {
      localStorage.removeItem("chat_messages_" + sessionId);
    } catch (e) {}
  }

  function exportConversation() {
    const payload = { session_id: sessionId, messages };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `conversation_${sessionId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function newSession() {
    const next = uuidv4();
    setSessionId(next);
    setMessages([]);
    setFeedback(null);
    setLiveTranscript("");
    setPendingTranscript(null);
    setEditableText("");
    if (audioRef.current) {
      audioRef.current.pause();
    }
    try {
      localStorage.setItem("chat_session_id", next);
      localStorage.removeItem("chat_messages_" + next);
    } catch (e) {}
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
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

      <main className="flex-1 p-4 max-w-3xl mx-auto w-full flex flex-col">
        <div ref={listRef} className="flex-1 overflow-auto mb-4 p-3 bg-white rounded-lg shadow-sm" style={{ minHeight: 300 }}>
          {messages.length === 0 && <div className="text-center text-slate-400 mt-20">Start the conversation by typing or speaking.</div>}

          <div className="space-y-3">
            {messages.map((m) => (
              <div key={m.id} className={`p-3 rounded-lg max-w-[80%] ${m.role === "user" ? "ml-auto bg-indigo-50" : "mr-auto bg-slate-100"}`}>
                <div className="text-sm whitespace-pre-wrap">{m.text}</div>
                <div className="text-[11px] text-slate-400 mt-1 text-right">{new Date(m.ts).toLocaleString()}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white p-3 rounded-lg shadow flex flex-col gap-2">
          {error && <div className="text-sm text-red-600 p-2 bg-red-50 rounded">{error}</div>}

          {liveTranscript && (
            <div className="p-2 bg-blue-50 rounded border border-blue-200">
              <div className="text-xs text-blue-600 font-semibold mb-1">🎤 Live Transcript:</div>
              <div className="text-sm text-blue-800">{liveTranscript}</div>
            </div>
          )}

          {/* NEW: Pending transcript editor */}
          {pendingTranscript && (
            <div className="p-3 bg-yellow-50 rounded border-2 border-yellow-400">
              <div className="flex items-center justify-between mb-2">
                <div className="text-xs font-semibold text-yellow-700">
                  ✏️ Review & Edit Transcript (Manual Mode)
                </div>
                <button 
                  onClick={handleCancelEdit}
                  className="text-xs text-yellow-600 hover:text-yellow-800"
                >
                  ✕ Cancel
                </button>
              </div>
              <textarea
                ref={editTextareaRef}
                value={editableText}
                onChange={(e) => setEditableText(e.target.value)}
                className="w-full p-2 rounded border border-yellow-300 resize-none focus:outline-none focus:ring-2 focus:ring-yellow-400"
                rows={3}
                placeholder="Edit your transcript here..."
              />
              <button
                onClick={handleSendEdited}
                disabled={!editableText.trim() || loading}
                className="mt-2 w-full px-4 py-2 bg-yellow-500 text-white rounded-md font-medium hover:bg-yellow-600 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                ✓ Send Edited Message
              </button>
            </div>
          )}

          {/* Regular text input - disabled when pending transcript exists */}
          <textarea 
            value={input} 
            onChange={(e) => setInput(e.target.value)} 
            onKeyDown={handleKeyDown} 
            placeholder="输入中文或英文（按 Enter 发送，Shift+Enter 换行）" 
            rows={3} 
            className="w-full p-2 rounded border resize-none focus:outline-none focus:ring disabled:bg-slate-100" 
            disabled={isRecording || pendingTranscript !== null}
          />

          <div className="flex items-center justify-between gap-3">
            <div className="flex gap-2 items-center flex-wrap">
              <button 
                onClick={sendMessage} 
                disabled={loading || isRecording || pendingTranscript !== null} 
                className="px-4 py-2 bg-emerald-500 text-white rounded-md disabled:opacity-60"
              >
                {loading ? "发送中... / Sending" : "发送 / Send Message"}
              </button>

              <button 
                onClick={isRecording ? stopRecording : startRecording} 
                disabled={pendingTranscript !== null}
                className={`px-3 py-2 rounded-md text-sm font-medium ${
                  isRecording 
                    ? "bg-red-500 text-white animate-pulse" 
                    : "bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-60"
                }`}
              >
                {isRecording ? "⏹ Stop Speaking" : "🎤 Start Speaking"}
              </button>

              {/* NEW: Auto-submit toggle button */}
              <button
                onClick={() => setAutoSubmit(!autoSubmit)}
                disabled={isRecording}
                className={`px-3 py-2 rounded-md text-sm font-medium border-2 transition-colors ${
                  autoSubmit
                    ? "bg-green-500 text-white border-green-600 hover:bg-green-600"
                    : "bg-white text-slate-700 border-slate-300 hover:bg-slate-50"
                } disabled:opacity-60`}
                title={autoSubmit ? "Auto-submit enabled: Transcripts sent immediately" : "Manual mode: Review transcripts before sending"}
              >
                {autoSubmit ? "⚡ Auto" : "✋ Manual"}
              </button>

              <button 
                onClick={endSession} 
                className="px-3 py-2 rounded-md text-sm bg-orange-400 text-white hover:bg-orange-500"
              >
                结束会话 / End Session
              </button>
            </div>

            <div className="text-sm text-slate-500">
              <div>Messages: {messages.length}</div>
              <div className="text-xs">
                Mode: {autoSubmit ? "🚀 Auto" : "✋ Manual"}
              </div>
            </div>
          </div>

          {feedback && (
            <div className="mt-2 border rounded p-3 bg-yellow-50">
              <h3 className="font-semibold">Session Feedback</h3>
              <pre className="text-sm whitespace-pre-wrap mt-1">{JSON.stringify(feedback, null, 2)}</pre>
            </div>
          )}
        </div>

        <footer className="text-xs text-center text-slate-400 mt-4">
          Make sure your backend is running at <span className="font-mono">http://localhost:5000</span>
          <div className="mt-1">
            {autoSubmit 
              ? "⚡ Auto-submit mode: Transcripts are sent immediately after recording" 
              : "✋ Manual mode: Review and edit transcripts before sending"}
          </div>
        </footer>
      </main>
    </div>
  );
}