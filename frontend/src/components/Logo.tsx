export default function Logo({ className = "h-8 w-auto" }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 200 50"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Icon - stylized "C" with gradient */}
      <defs>
        <linearGradient id="logoGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#7c3aed" />
          <stop offset="100%" stopColor="#8b5cf6" />
        </linearGradient>
      </defs>
      
      {/* Circular icon background */}
      <circle cx="25" cy="25" r="20" fill="url(#logoGradient)" />
      
      {/* "P" letter in white */}
      <path
        d="M20 15v20h3v-7h4c3.314 0 6-2.686 6-6s-2.686-6-6-6h-7zm3 3h4c1.657 0 3 1.343 3 3s-1.343 3-3 3h-4v-6z"
        fill="white"
      />
      
      {/* Text - "Prism" */}
      <text
        x="55"
        y="32"
        fontFamily="Plus Jakarta Sans, sans-serif"
        fontSize="24"
        fontWeight="700"
        fill="currentColor"
      >
        Prism
      </text>
    </svg>
  );
}