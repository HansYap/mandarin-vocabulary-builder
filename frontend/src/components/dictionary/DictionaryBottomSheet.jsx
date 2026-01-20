import { MobileDictionarySkeleton } from './DictionarySkeletons';
import DictionaryEntry from './DictionaryEntry';;


export default function DictionaryBottomSheet({ entry, loading, onClose }) {
    if (!loading && !entry) return null;

    return (
        <>
          {/* Dimmed Overlay */}
          <div
            onClick={onClose}
            className="fixed inset-0 bg-black/40 z-40"
          />

          {/* Bottom Sheet */}
          <div className="fixed bottom-0 left-0 right-0 bg-white rounded-t-2xl shadow-2xl z-50 max-h-[70vh] overflow-auto animate-slide-up">
            <div className="p-5">
              {loading ? (
                <MobileDictionarySkeleton />
              ) : entry && entry.found ? (
                <div>
                  {/* Word header */}
                  <div className="mb-4">
                    <div className="text-4xl font-bold text-slate-800 mb-2">
                      {entry.query || entry.simplified}
                    </div>
                  </div>

                    <DictionaryEntry entry={entry} size="large" />
                </div>
              ) : (
                <div className="text-center py-8">
                  <div className="text-lg text-slate-600 mb-2">Word not found</div>
                  <div className="text-sm text-slate-400">
                    {entry ? entry.message : ""}
                  </div>
                </div>
              )}
            </div>
          </div>

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
        `}</style>
        </>
    );
}