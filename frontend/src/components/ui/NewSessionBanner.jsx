export default function NewSessionBanner({ sessionEnded }) {
    if (!sessionEnded) return null;

    return (
        <div className="p-3 mb-2 rounded-md border border-orange-300 bg-orange-50 text-orange-800 text-sm rounded">
            ⚠️ This session has ended and feedback has been generated.
            <br />
            To receive <strong>new feedback</strong>, please click{" "}
            <span className="font-semibold">New Session</span>.
        </div>
    );
}