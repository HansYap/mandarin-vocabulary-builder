export default function LiveTranscriptBanner({ liveTranscript }) {
    if (!liveTranscript) return null;

    return (     
        <div className="p-2 bg-blue-50 rounded border border-blue-200">
            <div className="text-xs text-blue-600 font-semibold mb-1">🎤 Live Transcript:</div>
            <div className="text-sm text-blue-800">{liveTranscript}</div>
        </div>        
    );
}