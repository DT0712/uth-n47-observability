// Logo Obslab: ô vuông bo góc màu thanh menu, đường nhịp tim (tín hiệu giám sát) màu ngọc. Cùng hình với public/favicon.svg.
export function LogoMark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" className="logo-mark">
      <rect width="32" height="32" rx="8" fill="#1c2b3a" />
      <path d="M5 17.5h5l3-7.5 4.5 13 3-8.5 2 3H27" fill="none" stroke="#3ddbc4" strokeWidth="2.6"
            strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Brand({ size = 28 }: { size?: number }) {
  return (
    <span className="brand">
      <LogoMark size={size} />
      <span>Obslab <span className="brand-sub">Portal</span></span>
    </span>
  );
}
