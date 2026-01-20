import DictionaryPopover from './DictionaryPopover';
import DictionaryBottomSheet from './DictionaryBottomSheet';

export default function DictionaryContainer({ entry, loading, position, onClose, isMobile }) {
    if (isMobile) {
        return (
        <DictionaryBottomSheet entry={entry} loading={loading} onClose={onClose} />
        );
    }

    return (
        <DictionaryPopover
        entry={entry}
        loading={loading}
        position={position}
        onClose={onClose}
        />
    );
}