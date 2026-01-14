// src/components/dictionary/DictionarySkeletons.jsx
import { SkeletonBlock, SkeletonText } from "../Skeleton";

export const DesktopDictionarySkeleton = () => (
  <div className="space-y-4">
    <div className="flex items-start justify-between">
      <div className="space-y-2">
        <SkeletonBlock className="h-8 w-36" />
        <SkeletonBlock className="h-5 w-24" />
        <SkeletonBlock className="h-4 w-20" />
      </div>
      <SkeletonBlock className="h-6 w-6 rounded-full" />
    </div>

    <div className="border-t border-slate-100 pt-3">
      <SkeletonBlock className="h-4 w-24 mb-3" />
      <SkeletonText lines={3} />
    </div>
  </div>
);

export const MobileDictionarySkeleton = () => (
  <div className="space-y-5">
    <SkeletonBlock className="h-12 w-32" />
    <SkeletonBlock className="h-6 w-24" />

    <div className="border-t border-slate-100 pt-4">
      <SkeletonText lines={4} />
    </div>
  </div>
);
