export default function TranscriptEditor({ pendingTranscript, handleCancelEdit, editTextareaRef, loading, handleSendEdited, editableText, setEditableText }) {
    if (!pendingTranscript) return null;

    return (
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
           
    );
}