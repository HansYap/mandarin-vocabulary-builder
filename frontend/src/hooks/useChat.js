import { useState, useRef, useEffect } from 'react';
import { v4 as uuidv4 } from "uuid";

const API_BASE_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:5000";
const cleanBaseUrl = API_BASE_URL.replace(/\/$/, "");

export function useChat({ 
    sessionId, 
    messages, 
    setMessages, 
    setError, 
    audioRef,
}) {
    const listRef = useRef(null);
    const [loading, setLoading] = useState(false);

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
        const resp = await fetch(`${cleanBaseUrl}/api/chat`, {
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
        console.error("Chat error:", e);
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

    return {
        listRef,
        loading,
        setLoading,
        messages,
        setMessages,
        sendToChat,
        clearConversation,
        exportConversation,
    }
}