// ፩ (U+1369, Ethiopic digit one), the app's mark. The outline is taken from Noto Sans Ethiopic
// Medium (SIL Open Font License), so it needs no font at runtime and takes its color from CSS.

const PATH =
  'M17 625 53 786H515L551 625H528Q499 625 474 645Q449 665 436 704H132Q119 665 94 645Q69 625 39 625ZM276 121Q180 121 131 171Q82 221 82 300Q82 354 97 395Q112 436 137.5 472Q163 508 194 547L254 623H371L280 504Q353 497 395.5 468.5Q438 440 456.5 399Q475 358 475 313Q475 242 446.5 200Q418 158 372.5 139.5Q327 121 276 121ZM279 203Q320 203 346 228Q372 253 372 303Q372 335 359.5 362.5Q347 390 316 407.5Q285 425 230 428Q206 394 196 363.5Q186 333 186 302Q186 251 212.5 227Q239 203 279 203ZM14 -97 49 64H519L554 -97H532Q502 -97 477.5 -77Q453 -57 440 -17H128Q115 -57 90.5 -77Q66 -97 36 -97Z'

export function Logo({ size = 24 }: { size?: number }) {
  return (
    <svg
      className="logo"
      viewBox="14 -786 540 883"
      height={size}
      aria-hidden="true"
    >
      {/* Font outlines are y-up; SVG is y-down. */}
      <path d={PATH} transform="scale(1 -1)" fill="currentColor" />
    </svg>
  )
}
