export default function ErrorBanner({ error }) {
    if (!error) return null;

    return (
        <div className="p-2 bg-red-50 rounded border border-red-200">
            <div className="text-xs text-red-600 font-semibold mb-1">❌ Error:</div>
            <div className="text-sm text-red-800">{error}</div>
        </div>      
    );
}