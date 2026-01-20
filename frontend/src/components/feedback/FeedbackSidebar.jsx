import CorrectionCard from "./CorrectionCard";

export default function FeedbackSidebar({ feedbackItems, lookupDictionary, onExport, onClose }) {
    if (!feedbackItems) return null;
    
    return (
        <div className="w-96 bg-white rounded-lg shadow-sm p-4 overflow-auto" style={{ maxHeight: 'calc(100vh - 8rem)' }}>
            <div className="flex items-center justify-between mb-4 gap-2">
            <h2 className="text-lg font-bold text-slate-800">📊 Session Feedback</h2>

            <div className="flex items-center gap-2">
                <button
                onClick={onExport}
                className="px-2 py-1 text-xs rounded-md border border-slate-300 text-slate-600 hover:bg-slate-100"
                >
                Export
                </button>

                <button 
                onClick={onClose}
                className="text-slate-400 hover:text-slate-600 text-xl leading-none"
                >
                ×
                </button>
            </div>
            </div>
            
            {/* Sentence Corrections */}
            {feedbackItems.corrections && feedbackItems.corrections.length > 0 && (
            <div>
                <h3 className="text-md font-semibold text-slate-700 mb-3 flex items-center gap-2">
                ✏️ Feedback on sentences needing corrections ({feedbackItems.corrections.length})
                </h3>
                <div className="space-y-3">
                {feedbackItems.corrections.map((corr, idx) => (
                    <CorrectionCard key={idx} corr={corr} lookupDictionary={lookupDictionary} />
                ))}
                </div>
            </div>
            )}

            {/* Empty State */}
            {(!feedbackItems.corrections || feedbackItems.corrections.length === 0) && (
            <div className="text-center text-slate-400 py-8">
                No feedback items to display
            </div>
            )}
        </div>
    );
}