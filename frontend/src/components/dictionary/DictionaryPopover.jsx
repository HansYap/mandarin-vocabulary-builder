import { useRef, useEffect } from 'react';
import { DesktopDictionarySkeleton } from './DictionarySkeletons';
import DictionaryEntry from './DictionaryEntry';


export default function DictionaryPopover({ entry, loading, position, onClose }) {
    const popoverRef = useRef(null);

    // Close on outside click
    useEffect(() => {
        if (!position) return;

        const handleClickOutside = (e) => {
        if (popoverRef.current && !popoverRef.current.contains(e.target)) {
            onClose();
        }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [position, onClose]);

    if (!position) return null;

    return (
        <div
          ref={popoverRef}
          style={{
            position: 'absolute',
            top: `${position.top}px`,
            left: `${position.left}px`,
            zIndex: 1000,
          }}
          className="w-80 bg-white rounded-lg shadow-2xl border-2 border-purple-200 p-4 max-h-96 overflow-y-auto"
        >
            {loading ? (
                <DesktopDictionarySkeleton />
            ) : entry && entry.found ? (
                <div>
                <div className="flex items-start justify-between mb-3">
                    <div>
                    <div className="text-2xl font-bold text-slate-800">
                        {entry.query || entry.simplified}
                    </div>
                    </div>
                    <button
                    onClick={onClose}
                    className="text-slate-400 hover:text-slate-600 text-xl leading-none"
                    >
                    ×
                    </button>
                </div>
    
                <DictionaryEntry entry={entry} size="normal" />
                </div>
            ) : (
                <div className="text-center py-4">
                <div className="text-slate-600 mb-2">Word not found</div>
                <div className="text-xs text-slate-400">
                    {entry ? entry.message : "No entry"}
                </div>
                </div>
            )}
        </div>
    );
}