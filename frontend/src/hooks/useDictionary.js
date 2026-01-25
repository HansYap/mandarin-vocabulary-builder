import { useState, useRef, useEffect } from 'react';

const API_BASE_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:5000";

export function useDictionary() {
    const [dictionaryEntry, setDictionaryEntry] = useState(null);
    const [dictionaryLoading, setDictionaryLoading] = useState(false);
    const [popoverPosition, setPopoverPosition] = useState(null);
    const [isMobile, setIsMobile] = useState(false);
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


    async function lookupDictionary(word, event) {
        console.log("lookupDictionary called with:", word);

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
            `${API_BASE_URL}/api/dictionary/lookup`,
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
                console.error("Dictionary lookup failed:", err);
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


    return {
        dictionaryEntry,
        dictionaryLoading,
        popoverPosition,
        isMobile,
        lookupDictionary,
        closeDictionary,
    };
}       