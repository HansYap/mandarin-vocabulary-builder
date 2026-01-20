function classifierListFromEntry(entry) {
    if (!entry || !entry.classifier) return [];
    const cl = entry.classifier;
    if (Array.isArray(cl)) return cl;
    if (typeof cl === 'string') {
      return cl.split(',').map(s => s.trim()).filter(Boolean);
    }
    return [];
  }

export default function DictionaryEntry({ entry, size = 'normal' }) {
    if (!entry) return null;

    const isLarge = size === 'large';

    return (
        <div>
            {/* Display all entries */}
            {entry.entries && entry.entries.length > 0 ? (
            <div className={`${isLarge ? 'space-y-6' : 'space-y-4'}`}>
                {entry.entries.map((entryItem, entryIdx) => (
                <div 
                    key={entryIdx} 
                    className={`
                        ${isLarge ? 'pb-6' : 'pb-4'} 
                        ${entryIdx < entry.entries.length - 1 ? 'border-b border-slate-200' : ''}
                    `}
                >
                    {/* Pinyin with confidence badge */}
                    <div className={`${isLarge ? 'flex items-center gap-2 mb-3' : 'flex items-center gap-2 mb-2'}`}>
                    <div className={`${isLarge ? 'text-lg' : 'text-sm'} text-purple-600 font-medium`}>
                        {entryItem.pinyin}
                    </div>
                    {entryItem.confidence && (
                        <span className={`${isLarge ? 'text-sm px-2 py-1' : 'text-xs px-2 py-0.5'} rounded-full ${
                        entryItem.confidence === 'most common' || entryItem.confidence === 'most likely'
                            ? 'bg-green-100 text-green-700'
                            : entryItem.confidence === 'less common' || entryItem.confidence === 'alternative'
                            ? 'bg-slate-100 text-slate-600'
                            : 'bg-blue-100 text-blue-700'
                        }`}>
                        {entryItem.confidence}
                        </span>
                    )}
                    </div>

                    {/* Traditional (if different) */}
                    {entryItem.traditional && entryItem.traditional !== entryItem.simplified && (
                    <div className={`${isLarge ? 'text-xl text-slate-500 mb-3' : 'text-sm text-slate-500 mb-2'}`}>
                        {entryItem.traditional}
                    </div>
                    )}

                    {/* Definitions */}
                    <div className={`${isLarge ? 'mb-3' : 'mb-2'}`}>
                    <div className={`${isLarge ? 'text-sm font-semibold text-slate-600 mb-2' : 'text-xs font-semibold text-slate-600 mb-1'}`}>
                        Definitions & usage notes:
                    </div>
                    <ul className={`${isLarge ? 'space-y-2' : 'space-y-1'}`}>
                        {entryItem.definitions.map((def, i) => (
                        <li key={i} className={`${isLarge ? 'text-base text-slate-700 flex gap-3' : 'text-sm text-slate-700 flex gap-2'}`}>
                            <span className={`${isLarge ? 'text-purple-500 font-semibold' : 'text-purple-500 font-medium'}`}>{i + 1}.</span>
                            <span>{def}</span>
                        </li>
                        ))}
                    </ul>
                    </div>

                    {/* Classifier */}
                    {(() => {
                    const clList = classifierListFromEntry(entryItem);
                    if (!clList || clList.length === 0) return null;

                    return (
                        <div className={`${isLarge ? 'mt-3' : 'mt-2'}`}>
                        <div className={`${isLarge ? 'text-sm font-semibold text-slate-600 mb-2' : 'text-xs font-semibold text-slate-600 mb-1'}`}>
                            Classifier: (e.g. 一{clList[0].split('[')[0]}{entryItem.simplified})
                        </div>
                        <ul className={`${isLarge ? 'space-y-2' : 'space-y-1'}`}>
                            {clList.map((cl, idx) => (
                            <li key={idx} className={`${isLarge ? 'text-base text-slate-700 flex gap-3' : 'text-sm text-slate-700 flex gap-2'}`}>
                                <span className={`${isLarge ? 'text-purple-500 font-semibold' : 'text-purple-500 font-medium'}`}>{idx + 1}.</span>
                                <span>{cl}</span>
                            </li>
                            ))}
                        </ul>
                        </div>
                    );
                    })()}

                    {/* AI-generated badge */}
                    {entryItem.is_generated && (
                    <div className={`${isLarge ? 'mt-3 text-sm text-amber-700 bg-amber-50 p-3 rounded-lg border border-amber-200' 
                                               : 'mt-2 text-xs text-amber-600 bg-amber-50 p-2 rounded'}`}>
                        ⚡ AI-generated translation and pinyin
                    </div>
                    )}
                </div>
                ))}
            </div>
            ) : (
            // Fallback for old single-entry format
            <div>
                <div className={`${isLarge ? 'text-lg' : 'text-sm'} text-purple-600 mb-2`}>{entry.pinyin}</div>
                {entry.traditional !== entry.simplified && (
                <div className={`${isLarge ? 'text-xl text-slate-500 mb-3' : 'text-sm text-slate-500 mb-2'}`}>{entry.traditional}</div>
                )}
                <div className={`${isLarge ? 'pt-4' : 'pt-3'} border-t border-slate-200`}>
                <div className={`${isLarge ? 'text-sm mb-3' : 'text-xs mb-2'} font-semibold text-slate-600`}>Definitions:</div>
                <ul className={`${isLarge ? 'space-y-2' : 'space-y-1'}`}>
                    {entry.definitions?.map((def, i) => (
                    <li key={i} className={`${isLarge ? 'text-base gap-3' : 'text-sm gap-2'} text-slate-700 flex`}>
                        <span className={`${isLarge ? 'font-semibold' : 'font-medium'} text-purple-500`}>{i + 1}.</span>
                        <span>{def}</span>
                    </li>
                    ))}
                </ul>
                </div>
            </div>
            )}
        </div>
    );
}