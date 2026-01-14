// src/components/ui/Skeleton.jsx

export const SkeletonBlock = ({ className = "" }) => (
  <div className={`bg-slate-200 rounded animate-pulse ${className}`} />
);

export const SkeletonText = ({ lines = 3 }) => (
  <div className="space-y-2">
    {Array.from({ length: lines }).map((_, i) => (
      <SkeletonBlock
        key={i}
        className={`h-4 ${i === lines - 1 ? "w-3/4" : "w-full"}`}
      />
    ))}
  </div>
);
