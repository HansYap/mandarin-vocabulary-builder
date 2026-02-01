import { useState } from 'react';
import { v4 as uuidv4 } from "uuid";

const API_BASE_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:5000";
const cleanBaseUrl = API_BASE_URL.replace(/\/$/, "");

export function useSession({
    audioRef, 
    setMessages,
    setLiveTranscript,
    setPendingTranscript,
    setEditableText,
    closeDictionary,
    setError,
}) {
    const [feedback, setFeedback] = useState(null);
    const [sessionId, setSessionId] = useState(() => uuidv4());
    const [endingSession, setEndingSession] = useState(false);
    const [sessionEnded, setSessionEnded] = useState(false);

    async function endSession() {
        setError(null);
        setEndingSession(true);
        try {
        const resp = await fetch(`${cleanBaseUrl}/api/end-session`, {
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

    return { 
        feedback,
        sessionId,
        endingSession,
        sessionEnded,
        setFeedback,
        endSession,
        newSession,
        exportFeedback, 
    };
}