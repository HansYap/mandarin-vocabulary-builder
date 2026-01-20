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

export default function CorrectionCard({ corr, lookupDictionary }) {
    return (
        <div className="p-3 bg-gradient-to-br from-yellow-50 to-orange-50 rounded-lg border border-yellow-200">
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
    );
}


