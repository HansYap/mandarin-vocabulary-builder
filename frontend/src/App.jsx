import React, { useEffect, useRef, useState } from "react";
import { v4 as uuidv4 } from "uuid";
import { io } from "socket.io-client";
import Spinner from "./components/Spinner";
import {
  DesktopDictionarySkeleton,
  MobileDictionarySkeleton
} from "./components/dictionary/DictionarySkeletons";


const SOCKET_URL = "http://127.0.0.1:5000";

export default function App() {
  const [sessionId, setSessionId] = useState(() => uuidv4());
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [endingSession, setEndingSession] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [sessionEnded, setSessionEnded] = useState(false);
  const [error, setError] = useState(null);
  const [autoSubmit, setAutoSubmit] = useState(false);
  const [pendingTranscript, setPendingTranscript] = useState(null);
  const [editableText, setEditableText] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState("");
  
  // Dictionary lookup state
  const [dictionaryEntry, setDictionaryEntry] = useState(null);
  const [dictionaryLoading, setDictionaryLoading] = useState(false);
  const [popoverPosition, setPopoverPosition] = useState(null);
  const [isMobile, setIsMobile] = useState(false);

  const listRef = useRef(null);
  const audioRef = useRef(null);
  const socketRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);
  const editTextareaRef = useRef(null);
  const popoverRef = useRef(null);
  const dictionaryAbortRef = useRef(null);


  // Detect mobile
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Close dictionary on outside click (desktop only)
  useEffect(() => {
    if (!isMobile && popoverPosition) {
      const handleClickOutside = (e) => {
        if (popoverRef.current && !popoverRef.current.contains(e.target)) {
          closeDictionary();
        }
      };

      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [popoverPosition, isMobile]);


  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages, loading]);

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

  async function sendToChat(text, isEdited = false, originalText = null) {
    if (!text.trim()) return;

    const userMsg = {
      id: uuidv4(),
      role: "user",
      text,
      ts: new Date().toISOString(),
    };

    // Create a unique ID for the placeholder so we can find it later
    const placeholderId = uuidv4();
    const thinkingMsg = {
      id: placeholderId,
      role: "assistant",
      text: "Thinking...",
      isPlaceholder: true, // Custom flag for styling
      ts: new Date().toISOString(),
    };

    setMessages((m) => [...m, userMsg, thinkingMsg]);

    try {
      setLoading(true);
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
      
      if (!resp.ok) throw new Error(await resp.text() || resp.statusText);
      const d = await resp.json();
      
      // Replace the placeholder with the real response
      setMessages((prev) => 
        prev.map((msg) => 
          msg.id === placeholderId 
            ? { ...msg, text: d.response || d.message || "（无回复）", isPlaceholder: false }
            : msg
        )
      );
      
      if (d.audio) playAudio(d.audio);
    } catch (e) {
      console.error("❌ Chat error:", e);
      setError("无法联系后端: " + (e.message || e));
      // Update placeholder to show error
      setMessages((prev) => 
        prev.map((msg) => 
          msg.id === placeholderId 
            ? { ...msg, text: "抱歉，出了一点问题，稍后再试。", isPlaceholder: false }
            : msg
        )
      );
    } finally {
      setLoading(false);
    }
  }

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

    socket.on("final_transcript", async (data) => {
      console.log("✅ Final transcript (legacy):", data);
      const text = (data && data.text) || "";
      setLiveTranscript("");
      if (!text) return;
      await sendToChat(text);
    });

    socket.on("transcript_ready", async (data) => {
      console.log("✅ Transcript ready:", data);
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
        if (!e.data || e.data.size === 0) return;
        
        console.log(`📦 Chunk size: ${e.data.size} bytes`);

        try {
          const arrayBuffer = await e.data.arrayBuffer();
          const uint8 = new Uint8Array(arrayBuffer);
          
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
      setError("无法开启麦克风: (Please enable microphone usage for browser if not enabled) " + (e.message || e));
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

    const userMsg = {
      id: uuidv4(),
      role: "user",
      text,
      ts: new Date().toISOString(),
    };

    const placeholderId = uuidv4();
    const thinkingMsg = {
      id: placeholderId,
      role: "assistant",
      text: "Thinking...",
      isPlaceholder: true,
      ts: new Date().toISOString(),
    };

    setMessages((m) => [...m, userMsg, thinkingMsg]);
    setInput("");
    setLoading(true);

    try {
      const resp = await fetch("http://127.0.0.1:5000/api/chat/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, session_id: sessionId }),
      });

      if (!resp.ok) throw new Error(await resp.text() || resp.statusText);
      const data = await resp.json();

      setMessages((prev) => 
        prev.map((msg) => 
          msg.id === placeholderId 
            ? { ...msg, text: data.response || data.message || "（无回复）", isPlaceholder: false }
            : msg
        )
      );
      
      if (data.audio) playAudio(data.audio);
    } catch (e) {
      setError("无法联系后端: " + (e.message || e));
      setMessages((prev) => 
        prev.map((msg) => 
          msg.id === placeholderId 
            ? { ...msg, text: "抱歉，我好像遇到一点问题，你可以再说一次吗？", isPlaceholder: false }
            : msg
        )
      );
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
    setEndingSession(true);
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
      setSessionEnded(true);
    } catch (e) {
      console.error("End session error", e);
      setError("结束会话失败: " + (e.message || e));
    } finally {
      setEndingSession(false);
    }
  }

  async function lookupDictionary(word, event) {
    console.log("🔵 lookupDictionary called with:", word);

    // Abort previous request
    if (dictionaryAbortRef.current) {
      dictionaryAbortRef.current.abort();
    }

    const controller = new AbortController();
    dictionaryAbortRef.current = controller;

    // Position popover immediately (desktop)
    if (!isMobile && event) {
      const rect = event.target.getBoundingClientRect();
      setPopoverPosition({
        top: rect.bottom + window.scrollY + 8,
        left: rect.left + window.scrollX,
      });
    }

    setDictionaryEntry(null);
    setDictionaryLoading(true);

    try {
      const resp = await fetch(
        "http://127.0.0.1:5000/api/dictionary/lookup",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ word }),
          signal: controller.signal,
        }
      );

      const data = await resp.json();

      if (!controller.signal.aborted) {
        if (data.success && data.entry) {
          setDictionaryEntry(data.entry);
        } else {
          setDictionaryEntry({
            found: false,
            message: data.error || "Word not found",
          });
        }
      }
    } catch (err) {
      if (err.name !== "AbortError") {
        console.error("🔥 Dictionary lookup failed:", err);
        setDictionaryEntry({
          found: false,
          message: "Dictionary service unavailable",
        });
      }
    } finally {
      if (!controller.signal.aborted) {
        setDictionaryLoading(false);
      }
    }
  }

  function closeDictionary() {
    // Abort in-flight request
    if (dictionaryAbortRef.current) {
      dictionaryAbortRef.current.abort();
      dictionaryAbortRef.current = null;
    }

    setDictionaryLoading(false);
    setDictionaryEntry(null);
    setPopoverPosition(null);
  }

  function renderAnchoredText(text, onWordClick) {
    if (!text) return null;

    const parts = [];
    const regex = /\[\[(.*?)\]\]/g;

    let lastIndex = 0;
    let match;

    while ((match = regex.exec(text)) !== null) {
      const before = text.slice(lastIndex, match.index);
      if (before) {
        parts.push(before);
      }

      const word = match[1];

      parts.push(
        <span
          key={`${word}-${match.index}`}
          onClick={(e) => onWordClick(word, e)}
          className="cursor-pointer text-purple-600 font-semibold hover:underline hover:bg-indigo-50 px-1 rounded"
        >
          {word}
        </span>
      );

      lastIndex = regex.lastIndex;
    }

    const after = text.slice(lastIndex);
    if (after) {
      parts.push(after);
    }

    return parts;
  }

  function clearConversation() {
    setMessages([]);
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

  function exportFeedback() {
    if (!feedback) return;

    const payload = {
      session_id: sessionId,
      exported_at: new Date().toISOString(),
      feedback,
    };

    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: "application/json",
    });

    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `feedback_${sessionId}.json`;
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
    setSessionEnded(false);
    closeDictionary();

    if (audioRef.current) {
      audioRef.current.pause();
    }
  }

  // --- Helper: normalize classifier into an array for easy rendering ---
  function classifierListFromEntry(entry) {
    if (!entry || !entry.classifier) return [];
    const cl = entry.classifier;
    if (Array.isArray(cl)) return cl;
    if (typeof cl === 'string') {
      return cl.split(',').map(s => s.trim()).filter(Boolean);
    }
    return [];
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

      <main className="flex-1 p-4 max-w-5xl mx-auto w-full flex gap-4">
        {/* Chat Column */}
        <div className="flex-1 flex flex-col" style={{ maxHeight: 'calc(100vh - 8rem)' }}>
          <div ref={listRef} className="flex-1 overflow-auto mb-4 p-3 bg-white rounded-lg shadow-sm">
            {messages.length === 0 && <div className="text-center text-slate-400 mt-20">Start the conversation by typing or speaking.</div>}

            <div className="space-y-3">
              {messages.map((m) => (
                <div 
                  key={m.id} 
                  className={`p-3 rounded-lg max-w-[80%] transition-all duration-300 ${
                    m.role === "user" 
                      ? "ml-auto bg-indigo-50 border-transparent" 
                      : "mr-auto bg-slate-100 border-transparent"
                  } border`}
                >
                  <div className="text-sm whitespace-pre-wrap">
                    {m.isPlaceholder ? (
                      <div className="flex items-center gap-2 py-1">
                        <span className="text-slate-400 italic font-medium">Thinking</span>
                        <div className="flex">
                          <span className="dot"></span>
                          <span className="dot"></span>
                          <span className="dot"></span>
                        </div>
                      </div>
                    ) : (
                      m.text
                    )}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-1 text-right">
                    {new Date(m.ts).toLocaleString()}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white p-3 rounded-lg shadow flex flex-col gap-2">
            {error && (
              <div className="p-2 bg-red-50 rounded border border-red-200">
                <div className="text-xs text-red-600 font-semibold mb-1">❌ Error:</div>
                <div className="text-sm text-red-800">{error}</div>
              </div>
            )}

            {sessionEnded && (
              <div className="p-3 mb-2 rounded-md border border-orange-300 bg-orange-50 text-orange-800 text-sm rounded">
                ⚠️ This session has ended and feedback has been generated.
                <br />
                To receive <strong>new feedback</strong>, please click{" "}
                <span className="font-semibold">New Session</span>.
              </div>
            )}

            {liveTranscript && (
              <div className="p-2 bg-blue-50 rounded border border-blue-200">
                <div className="text-xs text-blue-600 font-semibold mb-1">🎤 Live Transcript:</div>
                <div className="text-sm text-blue-800">{liveTranscript}</div>
              </div>
            )}

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

            <textarea 
              value={input} 
              onChange={(e) => setInput(e.target.value)} 
              onKeyDown={handleKeyDown} 
              placeholder="输入中文或英文（按 Enter 发送，Shift+Enter 换行）" 
              rows={3} 
              className="w-full p-2 rounded border resize-none focus:outline-none focus:ring disabled:bg-slate-100 disabled:opacity-60 disabled:cursor-not-allowed" 
              disabled={isRecording || pendingTranscript !== null || loading || endingSession}
            />

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
          </div>
        </div>

        {/* Feedback Sidebar */}
        {feedback && (
          <div className="w-96 bg-white rounded-lg shadow-sm p-4 overflow-auto" style={{ maxHeight: 'calc(100vh - 8rem)' }}>
            <div className="flex items-center justify-between mb-4 gap-2">
              <h2 className="text-lg font-bold text-slate-800">📊 Session Feedback</h2>

              <div className="flex items-center gap-2">
                <button
                  onClick={exportFeedback}
                  className="px-2 py-1 text-xs rounded-md border border-slate-300 text-slate-600 hover:bg-slate-100"
                >
                  Export
                </button>

                <button 
                  onClick={() => setFeedback(null)}
                  className="text-slate-400 hover:text-slate-600 text-xl leading-none"
                >
                  ×
                </button>
              </div>
            </div>
            
            {/* Sentence Corrections */}
            {feedback.corrections && feedback.corrections.length > 0 && (
              <div>
                <h3 className="text-md font-semibold text-slate-700 mb-3 flex items-center gap-2">
                  ✏️ Feedback on sentences needing corrections ({feedback.corrections.length})
                </h3>
                <div className="space-y-3">
                  {feedback.corrections.map((corr, idx) => (
                    <div key={idx} className="p-3 bg-gradient-to-br from-yellow-50 to-orange-50 rounded-lg border border-yellow-200">
                      <div className="text-xs text-amber-700 font-semibold mb-1">你说的 (What you said):</div>
                      <div className="text-sm text-slate-600 mb-3 line-through opacity-70">
                        {corr.original_sentence}
                      </div>
                      <div className="text-xs text-green-700 font-semibold mb-1">更自然的说法 (Natural way):</div>
                      <div className="text-base font-medium text-slate-800 mb-2 leading-relaxed">
                        {renderAnchoredText(corr.corrected_sentence, lookupDictionary)}
                      </div>
                      {corr.explanation && (
                        <div className="text-sm text-amber-700 bg-white/50 p-2 rounded">
                          💡 {corr.explanation}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Empty State */}
            {(!feedback.corrections || feedback.corrections.length === 0) && (
              <div className="text-center text-slate-400 py-8">
                No feedback items to display
              </div>
            )}
          </div>
        )}
      </main>

      {/* Desktop Popover */}
        {!isMobile && popoverPosition && (
          <div
            ref={popoverRef}
            style={{
              position: 'absolute',
              top: `${popoverPosition.top}px`,
              left: `${popoverPosition.left}px`,
              zIndex: 1000,
            }}
            className="w-80 bg-white rounded-lg shadow-2xl border-2 border-purple-200 p-4"
          >
            {dictionaryLoading ? (
              // Pulsing skeleton placeholder
              <DesktopDictionarySkeleton />
            ) : dictionaryEntry && dictionaryEntry.found ? (
              // real content (unchanged)
              <div>
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="text-2xl font-bold text-slate-800">{dictionaryEntry.simplified}</div>
                    {dictionaryEntry.traditional !== dictionaryEntry.simplified && (
                      <div className="text-lg text-slate-500">{dictionaryEntry.traditional}</div>
                    )}
                    <div className="text-sm text-purple-600 mt-1">{dictionaryEntry.pinyin}</div>
                  </div>
                  <button
                    onClick={closeDictionary}
                    className="text-slate-400 hover:text-slate-600 text-xl leading-none"
                  >
                    ×
                  </button>
                </div>

                <div className="border-t border-slate-200 pt-3">
                  <div className="text-xs font-semibold text-slate-600 mb-2">Definitions:</div>
                  <ul className="space-y-1">
                    {dictionaryEntry.definitions.map((def, i) => (
                      <li key={i} className="text-sm text-slate-700 flex gap-2">
                        <span className="text-purple-500 font-medium">{i + 1}.</span>
                        <span>{def}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* NEW: Classifier section (styled like Definitions) */}
                {(() => {
                  const clList = classifierListFromEntry(dictionaryEntry);
                  if (!clList || clList.length === 0) return null;

                  return (
                    <div className="border-t border-slate-200 pt-3 mt-3">
                      <div className="text-xs font-semibold text-slate-600 mb-2">Classifier: (e.g. 一{clList[0]}{dictionaryEntry.simplified})</div>
                      <ul className="space-y-1">
                        {clList.map((cl, idx) => (
                          <li key={idx} className="text-sm text-slate-700 flex gap-2">
                            <span className="text-purple-500 font-medium">{idx + 1}.</span>
                            <span>{cl}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  );
                })()}

                {dictionaryEntry.is_generated && (
                  <div className="mt-3 text-xs text-amber-600 bg-amber-50 p-2 rounded">
                    ⚡ AI-generated translation and pinyin
                  </div>
                )}
              </div>
            ) : (
              // not found / error
              <div className="text-center py-4">
                <div className="text-slate-600 mb-2">Word not found</div>
                <div className="text-xs text-slate-400">{dictionaryEntry ? dictionaryEntry.message : "No entry"}</div>
              </div>
            )}
          </div>
        )}


      {/* Mobile Bottom Sheet */}
        {isMobile && (dictionaryLoading || dictionaryEntry) && (
          <>
            {/* Dimmed Overlay */}
            <div
              onClick={closeDictionary}
              className="fixed inset-0 bg-black/40 z-40"
            />

            {/* Bottom Sheet */}
            <div className="fixed bottom-0 left-0 right-0 bg-white rounded-t-2xl shadow-2xl z-50 max-h-[70vh] overflow-auto animate-slide-up">
              <div className="p-5">
                {dictionaryLoading ? (
                  // Mobile skeleton
                  <MobileDictionarySkeleton />
                ) : dictionaryEntry && dictionaryEntry.found ? (
                  // real content (unchanged)
                  <div>
                    <div className="mb-4">
                      <div className="text-4xl font-bold text-slate-800 mb-2">{dictionaryEntry.simplified}</div>
                      {dictionaryEntry.traditional !== dictionaryEntry.simplified && (
                        <div className="text-2xl text-slate-500 mb-2">{dictionaryEntry.traditional}</div>
                      )}
                      <div className="text-lg text-purple-600">{dictionaryEntry.pinyin}</div>
                    </div>

                    <div className="border-t border-slate-200 pt-4">
                      <div className="text-sm font-semibold text-slate-600 mb-3">Definitions:</div>
                      <ul className="space-y-2">
                        {dictionaryEntry.definitions.map((def, i) => (
                          <li key={i} className="text-base text-slate-700 flex gap-3">
                            <span className="text-purple-500 font-semibold">{i + 1}.</span>
                            <span>{def}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    {/* NEW: Classifier section for mobile */}
                    {(() => {
                      const clList = classifierListFromEntry(dictionaryEntry);
                      if (!clList || clList.length === 0) return null;

                      return (
                        <div className="border-t border-slate-200 pt-4 mt-4">
                          <div className="text-sm font-semibold text-slate-600 mb-3">Classifier:</div>
                          <ul className="space-y-2">
                            {clList.map((cl, idx) => (
                              <li key={idx} className="text-base text-slate-700 flex gap-3">
                                <span className="text-purple-500 font-semibold">{idx + 1}.</span>
                                <span>{cl}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      );
                    })()}

                    {dictionaryEntry.is_generated && (
                      <div className="mt-4 text-sm text-amber-700 bg-amber-50 p-3 rounded-lg border border-amber-200">
                        ⚡ AI-generated translation and pinyin
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-8">
                    <div className="text-lg text-slate-600 mb-2">Word not found</div>
                    <div className="text-sm text-slate-400">{dictionaryEntry ? dictionaryEntry.message : ""}</div>
                  </div>
                )}
              </div>
            </div>
          </>
        )}


      <style jsx>{`
        @keyframes slide-up {
          from {
            transform: translateY(100%);
          }
          to {
            transform: translateY(0);
          }
        }
        .animate-slide-up {
          animation: slide-up 0.3s ease-out;
        }

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
    </div>
  );
}