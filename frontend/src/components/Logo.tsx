export default function Logo({ className = "h-8 w-auto" }: { className?: string }) {
  return (
    <div className={`flex items-center space-x-3 ${className}`}>
      {/* Prism Logo Icon */}
      <svg
        viewBox="0 0 32 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="w-8 h-8"
      >
        <defs>
          <linearGradient id="prismGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#8b5cf6" />
            <stop offset="25%" stopColor="#a855f7" />
            <stop offset="50%" stopColor="#ec4899" />
            <stop offset="75%" stopColor="#06b6d4" />
            <stop offset="100%" stopColor="#10b981" />
          </linearGradient>
          <linearGradient id="prismShadow" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="rgba(139, 92, 246, 0.3)" />
            <stop offset="100%" stopColor="rgba(139, 92, 246, 0.1)" />
          </linearGradient>
        </defs>
        
        {/* Main prism shape */}
        <path
          d="M16 4 L28 14 L16 24 L4 14 Z"
          fill="url(#prismGradient)"
          className="drop-shadow-sm"
        />
        
        {/* Prism facets for depth */}
        <path d="M16 4 L24 8 L16 12 Z" fill="rgba(139, 92, 246, 0.8)" />
        <path d="M16 12 L24 16 L16 20 Z" fill="rgba(168, 85, 247, 0.8)" />
        <path d="M16 20 L24 24 L16 24 Z" fill="rgba(236, 72, 153, 0.8)" />
        
        {/* Subtle glow effect */}
        <circle cx="16" cy="14" r="12" fill="url(#prismShadow)" className="opacity-50" />
      </svg>
      
      {/* Text - "Prism" */}
      <span className="text-xl font-display font-bold text-neutral-900">
        Prism
      </span>
    </div>
  );
}