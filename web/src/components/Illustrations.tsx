// Original flat illustrations in the Swayam-sevak palette. Decorative unless given a title.
import type { SVGProps } from "react";

const C = {
  saffron: "#FF9933", saffronSoft: "#FFD3A3", saffronPale: "#FFF1E0",
  leaf: "#138808", leafSoft: "#B0DFA6", leafPale: "#E6F5E2",
  navy: "#13306B", navySoft: "#B9C8EC", navyPale: "#EEF2FB",
  skin: "#C98E64", skinLight: "#E7B48C", hair: "#1E1B2E", white: "#FFFFFF", line: "#DCE4F6",
};

type P = SVGProps<SVGSVGElement> & { title?: string };
const a11y = (title?: string) => (title ? { role: "img", "aria-label": title } : { "aria-hidden": true });

/** Hero: a citizen with her phone while the agent fills a portal form; OTP bubble, shield, signed receipt. */
export function HeroScene({ title, ...p }: P) {
  return (
    <svg viewBox="0 0 540 440" {...a11y(title)} {...p}>
      <defs>
        <linearGradient id="hs-blob" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor={C.saffronPale} />
          <stop offset="1" stopColor={C.leafPale} />
        </linearGradient>
        <filter id="hs-soft" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="10" stdDeviation="12" floodColor={C.navy} floodOpacity="0.14" />
        </filter>
      </defs>
      <path d="M58 140C70 60 170 18 270 30s230 40 246 140-40 210-150 236-250 24-300-40S46 220 58 140Z" fill="url(#hs-blob)" />
      {/* browser window */}
      <g filter="url(#hs-soft)">
        <rect x="170" y="62" width="330" height="246" rx="20" fill={C.white} />
        <rect x="170" y="62" width="330" height="40" rx="20" fill={C.navyPale} />
        <rect x="170" y="86" width="330" height="16" fill={C.navyPale} />
        <circle cx="194" cy="82" r="5" fill="#F87171" /><circle cx="211" cy="82" r="5" fill="#FBBF24" /><circle cx="228" cy="82" r="5" fill="#34D399" />
        <rect x="248" y="72" width="200" height="20" rx="10" fill={C.white} />
        <path d="M258 82h4" stroke={C.leaf} strokeWidth="6" strokeLinecap="round" />
        <rect x="270" y="79" width="120" height="6" rx="3" fill={C.navySoft} />
      </g>
      {[0, 1, 2, 3].map((i) => (
        <g key={i} transform={`translate(196 ${122 + i * 44})`}>
          <rect width="90" height="8" rx="4" fill={C.navySoft} />
          <rect y="14" width="230" height="20" rx="8" fill={i === 3 ? C.saffronPale : C.navyPale} stroke={i === 3 ? C.saffron : "none"} strokeWidth="2" />
          {i < 3 ? (
            <>
              <rect x="10" y="20" width={[110, 80, 140][i]} height="8" rx="4" fill={C.navy} opacity="0.55" />
              <circle cx="262" cy="24" r="11" fill={C.leaf} />
              <path d="M256 24l4 4 8-8" stroke={C.white} strokeWidth="3" fill="none" strokeLinecap="round" strokeLinejoin="round" />
            </>
          ) : (
            <>
              <rect x="10" y="20" width="56" height="8" rx="4" fill={C.navy} opacity="0.55" />
              <rect x="70" y="18" width="3" height="12" rx="1.5" fill={C.saffron} />
            </>
          )}
        </g>
      ))}
      {/* agent cursor with sparkle */}
      <path d="M352 268l0 34 9-9 7 15 7-3-7-15 13 0z" fill={C.navy} stroke={C.white} strokeWidth="2" strokeLinejoin="round" />
      <path d="M392 250l3 8 8 3-8 3-3 8-3-8-8-3 8-3z" fill={C.saffron} />
      {/* shield badge */}
      <g transform="translate(470 40)" filter="url(#hs-soft)">
        <path d="M0 -24 22 -16v18c0 16-10 26-22 32C-12 28-22 18-22 2v-18z" fill={C.leaf} />
        <path d="M-9 2l6 6 12-13" stroke={C.white} strokeWidth="4" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      </g>
      {/* signed receipt */}
      <g transform="translate(408 300) rotate(8)" filter="url(#hs-soft)">
        <rect width="96" height="112" rx="12" fill={C.white} />
        <rect x="14" y="16" width="52" height="7" rx="3.5" fill={C.navy} opacity="0.7" />
        {[32, 44, 56].map((y) => <rect key={y} x="14" y={y} width="68" height="5" rx="2.5" fill={C.navySoft} />)}
        <circle cx="66" cy="86" r="15" fill={C.saffron} />
        <path d="M59 86l5 5 9-10" stroke={C.white} strokeWidth="3" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      </g>
      {/* citizen */}
      <ellipse cx="112" cy="404" rx="76" ry="11" fill={C.navy} opacity="0.08" />
      <rect x="90" y="300" width="20" height="96" rx="9" fill={C.navy} />
      <rect x="116" y="300" width="20" height="96" rx="9" fill={C.navy} />
      <ellipse cx="98" cy="398" rx="15" ry="7" fill={C.hair} /><ellipse cx="130" cy="398" rx="15" ry="7" fill={C.hair} />
      <path d="M78 196Q112 180 146 196L160 324Q112 340 64 324Z" fill={C.saffron} />
      <path d="M84 198 142 306 128 314 74 216Z" fill={C.leaf} opacity="0.92" />
      <path d="M84 206Q70 246 74 280" stroke={C.skin} strokeWidth="15" strokeLinecap="round" fill="none" />
      <path d="M140 204Q160 220 172 236" stroke={C.skin} strokeWidth="15" strokeLinecap="round" fill="none" />
      <rect x="104" y="170" width="16" height="22" rx="6" fill={C.skin} />
      <circle cx="112" cy="156" r="27" fill={C.skin} />
      <path d="M85 154c0-22 14-34 30-34 16 0 26 12 26 28-6-8-20-12-34-10-10 2-16 8-22 16z" fill={C.hair} />
      <circle cx="136" cy="128" r="11" fill={C.hair} />
      <circle cx="103" cy="160" r="2.6" fill={C.hair} /><circle cx="121" cy="160" r="2.6" fill={C.hair} />
      <path d="M105 172q7 6 14 0" stroke={C.hair} strokeWidth="2.4" fill="none" strokeLinecap="round" />
      <g transform="translate(160 208) rotate(-10)">
        <rect width="30" height="52" rx="6" fill={C.navy} />
        <rect x="4" y="6" width="22" height="38" rx="3" fill={C.white} />
        <circle cx="15" cy="25" r="7" fill={C.leaf} />
        <path d="M11 25l3 3 5-6" stroke={C.white} strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      </g>
      {/* OTP bubble */}
      <g transform="translate(36 70)" filter="url(#hs-soft)">
        <rect width="104" height="46" rx="14" fill={C.white} />
        <path d="M70 46l10 14 2-14z" fill={C.white} />
        {[0, 1, 2, 3].map((i) => <circle key={i} cx={22 + i * 20} cy="23" r="5" fill={i < 3 ? C.navy : C.saffron} />)}
      </g>
    </svg>
  );
}

/** Pillar 1: know your rights — an open book, Hindi/English bubbles and a magnifier. */
export function KnowArt({ title, ...p }: P) {
  return (
    <svg viewBox="0 0 160 130" {...a11y(title)} {...p}>
      <ellipse cx="80" cy="118" rx="58" ry="7" fill={C.navy} opacity="0.08" />
      <path d="M20 40q30-12 58 4v66q-28-14-58-4z" fill={C.white} stroke={C.navySoft} strokeWidth="3" />
      <path d="M140 40q-30-12-58 4v66q28-14 58-4z" fill={C.white} stroke={C.navySoft} strokeWidth="3" />
      {[56, 68, 80].map((y) => <path key={y} d={`M32 ${y}q16-6 36 2`} stroke={C.navySoft} strokeWidth="4" fill="none" strokeLinecap="round" />)}
      {[56, 68].map((y) => <path key={y} d={`M92 ${y + 2}q18-8 36-2`} stroke={C.leafSoft} strokeWidth="4" fill="none" strokeLinecap="round" />)}
      <rect x="18" y="6" width="34" height="26" rx="9" fill={C.saffron} />
      <text x="35" y="25" textAnchor="middle" fontSize="15" fontWeight="700" fill={C.white} fontFamily="Mukta, sans-serif">अ</text>
      <rect x="58" y="2" width="30" height="24" rx="9" fill={C.navy} />
      <text x="73" y="20" textAnchor="middle" fontSize="14" fontWeight="700" fill={C.white} fontFamily="Mukta, sans-serif">A</text>
      <circle cx="118" cy="86" r="16" fill={C.leafPale} stroke={C.leaf} strokeWidth="5" />
      <path d="M130 98l14 14" stroke={C.leaf} strokeWidth="7" strokeLinecap="round" />
      <path d="M111 86l5 5 9-10" stroke={C.leaf} strokeWidth="3.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** Pillar 2: report a problem — phone camera framing a pothole, with a map pin. */
export function ReportArt({ title, ...p }: P) {
  return (
    <svg viewBox="0 0 160 130" {...a11y(title)} {...p}>
      <ellipse cx="80" cy="118" rx="58" ry="7" fill={C.navy} opacity="0.08" />
      <path d="M10 104 50 66h60l40 38z" fill="#9AA3B5" />
      <path d="M80 70v8m0 8v8m0 8v6" stroke={C.white} strokeWidth="3" strokeLinecap="round" />
      <ellipse cx="104" cy="94" rx="16" ry="6" fill="#4B5568" />
      <rect x="34" y="14" width="56" height="88" rx="10" fill={C.navy} transform="rotate(-8 62 58)" />
      <rect x="40" y="22" width="44" height="64" rx="6" fill={C.saffronPale} transform="rotate(-8 62 58)" />
      <path d="M44 34h8M44 34v8M80 30h-8M80 30v8M48 76h8M48 76v-8M84 72h-8M84 72v-8" stroke={C.saffron} strokeWidth="3" strokeLinecap="round" transform="rotate(-8 62 58)" />
      <ellipse cx="62" cy="56" rx="12" ry="5" fill="#4B5568" transform="rotate(-8 62 58)" />
      <path d="M128 20c-11 0-19 8-19 19 0 14 19 32 19 32s19-18 19-32c0-11-8-19-19-19z" fill={C.saffron} />
      <circle cx="128" cy="39" r="7" fill={C.white} />
    </svg>
  );
}

/** Pillar 3: the agent fills the portal — browser, cursor, gear and a check. */
export function AgentArt({ title, ...p }: P) {
  return (
    <svg viewBox="0 0 160 130" {...a11y(title)} {...p}>
      <ellipse cx="80" cy="118" rx="58" ry="7" fill={C.navy} opacity="0.08" />
      <rect x="14" y="14" width="124" height="92" rx="12" fill={C.white} stroke={C.navySoft} strokeWidth="3" />
      <path d="M14 34h124" stroke={C.navySoft} strokeWidth="3" />
      <circle cx="26" cy="24" r="3.5" fill="#F87171" /><circle cx="37" cy="24" r="3.5" fill="#FBBF24" /><circle cx="48" cy="24" r="3.5" fill="#34D399" />
      {[46, 64, 82].map((y, i) => (
        <g key={y}>
          <rect x="26" y={y} width="72" height="11" rx="5" fill={i < 2 ? C.leafPale : C.saffronPale} />
          {i < 2 && <path d={`M106 ${y + 5}l3 3 6-7`} stroke={C.leaf} strokeWidth="3" fill="none" strokeLinecap="round" strokeLinejoin="round" />}
        </g>
      ))}
      <path d="M96 84v24l7-7 5 11 5-2-5-11h10z" fill={C.navy} stroke={C.white} strokeWidth="1.6" strokeLinejoin="round" />
      <g transform="translate(132 98)">
        <circle r="16" fill={C.leaf} />
        <path d="M-7 0l5 5 9-10" stroke={C.white} strokeWidth="3.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      </g>
    </svg>
  );
}

/** "How it works" step art. */
export function StepArt({ step, ...p }: P & { step: 1 | 2 | 3 | 4 }) {
  return (
    <svg viewBox="0 0 96 80" aria-hidden {...p}>
      <ellipse cx="48" cy="72" rx="32" ry="5" fill={C.navy} opacity="0.08" />
      {step === 1 && (
        <>
          <rect x="8" y="10" width="54" height="30" rx="12" fill={C.navy} />
          <path d="M20 40l-4 10 12-10z" fill={C.navy} />
          {[22, 34, 46].map((x) => <circle key={x} cx={x} cy="25" r="3.5" fill={C.white} />)}
          <rect x="38" y="32" width="50" height="28" rx="12" fill={C.saffron} />
          <path d="M76 60l4 9-12-9z" fill={C.saffron} />
          <text x="63" y="51" textAnchor="middle" fontSize="13" fontWeight="700" fill={C.white} fontFamily="Mukta, sans-serif">नमस्ते</text>
        </>
      )}
      {step === 2 && (
        <>
          <rect x="14" y="6" width="68" height="60" rx="9" fill={C.white} stroke={C.navySoft} strokeWidth="2.5" />
          {[18, 32, 46].map((y, i) => <rect key={y} x="22" y={y} width="52" height="9" rx="4" fill={i < 2 ? C.leafPale : C.saffronPale} />)}
          <path d="M62 44v18l5-5 4 8 4-2-4-8h7z" fill={C.navy} stroke={C.white} strokeWidth="1.2" />
        </>
      )}
      {step === 3 && (
        <>
          <rect x="30" y="2" width="36" height="66" rx="8" fill={C.navy} />
          <rect x="34" y="9" width="28" height="48" rx="4" fill={C.white} />
          <circle cx="48" cy="33" r="11" fill={C.leaf} />
          <path d="M42 33l4 4 8-9" stroke={C.white} strokeWidth="3" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        </>
      )}
      {step === 4 && (
        <>
          <rect x="20" y="4" width="52" height="64" rx="8" fill={C.white} stroke={C.navySoft} strokeWidth="2.5" />
          {[16, 26, 36].map((y) => <rect key={y} x="28" y={y} width="34" height="5" rx="2.5" fill={C.navySoft} />)}
          <circle cx="62" cy="56" r="13" fill={C.saffron} />
          <path d="M56 56l4 4 7-8" stroke={C.white} strokeWidth="3" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        </>
      )}
    </svg>
  );
}

/** Eligibility pre-check: a citizen answers a short, source-backed questionnaire on a phone. */
export function EligibilityArt({ title, ...p }: P) {
  return (
    <svg viewBox="0 0 220 170" {...a11y(title)} {...p}>
      <ellipse cx="110" cy="154" rx="82" ry="9" fill={C.navy} opacity="0.16" />
      <path d="M22 104C26 42 88 15 149 30s65 75 33 105-140 29-160-31Z" fill={C.navy} opacity="0.2" />
      <rect x="119" y="20" width="62" height="112" rx="13" fill={C.white} stroke={C.navySoft} strokeWidth="3" />
      <rect x="126" y="32" width="48" height="15" rx="5" fill={C.saffronPale} />
      {[58, 75, 92].map((y, i) => <g key={y}><rect x="128" y={y} width="32" height="6" rx="3" fill={C.navySoft} /><circle cx="169" cy={y + 3} r="5" fill={i < 2 ? C.leaf : C.saffron} /></g>)}
      <path d="M84 72q19-11 39 0l8 58q-26 12-53 0z" fill={C.saffron} />
      <path d="M91 74 121 129l-12 4-29-49z" fill={C.leaf} opacity="0.9" />
      <circle cx="101" cy="51" r="19" fill={C.skin} />
      <path d="M83 51c0-16 12-24 22-22 12 2 17 12 14 25-5-7-13-10-24-8-6 1-9 3-12 5z" fill={C.hair} />
      <rect x="94" y="66" width="13" height="12" rx="4" fill={C.skin} />
      <rect x="84" y="127" width="15" height="25" rx="7" fill={C.navy} /><rect x="109" y="127" width="15" height="25" rx="7" fill={C.navy} />
      <path d="M116 84q16 4 23 16" stroke={C.skin} strokeWidth="10" fill="none" strokeLinecap="round" />
      <g transform="translate(48 39)"><rect width="47" height="29" rx="12" fill={C.leaf} /><path d="M15 14l5 5 11-12" stroke={C.white} strokeWidth="3" fill="none" strokeLinecap="round" strokeLinejoin="round" /></g>
    </svg>
  );
}

/** Accountability teaser: a signed receipt and map pin, illustrating traceable outcomes. */
export function ReceiptArt({ title, ...p }: P) {
  return (
    <svg viewBox="0 0 230 190" {...a11y(title)} {...p}>
      <ellipse cx="115" cy="172" rx="84" ry="10" fill={C.white} opacity="0.13" />
      <path d="M18 128 82 42l126 71-55 47z" fill={C.navySoft} opacity="0.55" />
      <path d="m51 142 68-76m-16 91 67-76" stroke={C.white} strokeWidth="4" opacity="0.75" />
      <rect x="70" y="25" width="91" height="122" rx="14" fill={C.white} stroke={C.saffronSoft} strokeWidth="3" transform="rotate(6 115 86)" />
      {[53, 67, 81, 95].map((y, i) => <rect key={y} x="88" y={y} width={i === 0 ? 40 : 54} height="6" rx="3" fill={i === 0 ? C.navy : C.navySoft} transform="rotate(6 115 86)" />)}
      <g transform="translate(133 119)"><circle r="19" fill={C.leaf} /><path d="M-9 0l6 6 12-14" stroke={C.white} strokeWidth="4" fill="none" strokeLinecap="round" strokeLinejoin="round" /></g>
      <path d="M39 49c-13 0-24 10-24 24 0 18 24 42 24 42s24-24 24-42c0-14-11-24-24-24z" fill={C.saffron} /><circle cx="39" cy="73" r="8" fill={C.white} />
    </svg>
  );
}

export type Category = "Road and Bridges" | "Water Supply" | "Sanitation and Garbage" | "Street Lights" | "Pollution" | "Other";

/** Clay-style category icons for grievance tiles. */
export function CategoryArt({ category, ...p }: P & { category: Category }) {
  return (
    <svg viewBox="0 0 80 80" aria-hidden {...p}>
      {category === "Road and Bridges" && (
        <>
          <path d="M6 66 30 22h20l24 44z" fill="#8F99AE" />
          <path d="M40 26v8m0 8v8m0 8v6" stroke={C.white} strokeWidth="3" strokeLinecap="round" />
          <path d="M22 54l6-4 4 5 6-3" stroke="#3E4659" strokeWidth="2.5" fill="none" strokeLinecap="round" />
          <path d="M60 30 66 52h-12z" fill={C.saffron} /><rect x="56" y="38" width="8" height="4" fill={C.white} />
          <rect x="51" y="52" width="18" height="5" rx="2" fill={C.navy} />
        </>
      )}
      {category === "Water Supply" && (
        <>
          <rect x="10" y="20" width="34" height="12" rx="6" fill={C.navy} />
          <rect x="36" y="20" width="12" height="26" rx="5" fill={C.navy} />
          <rect x="22" y="12" width="10" height="10" rx="3" fill={C.saffron} />
          <path d="M42 50c0 0-9 11-9 17a9 9 0 0 0 18 0c0-6-9-17-9-17z" fill="#3B82F6" />
          <path d="M60 30c0 0-6 7-6 11a6 6 0 0 0 12 0c0-4-6-11-6-11z" fill="#93C5FD" />
        </>
      )}
      {category === "Sanitation and Garbage" && (
        <>
          <rect x="20" y="24" width="40" height="44" rx="8" fill={C.leaf} />
          <rect x="16" y="16" width="48" height="10" rx="5" fill={C.navy} />
          <rect x="34" y="10" width="12" height="8" rx="3" fill={C.navy} />
          {[30, 40, 50].map((x) => <rect key={x} x={x - 2} y="32" width="4" height="28" rx="2" fill={C.white} opacity="0.7" />)}
        </>
      )}
      {category === "Street Lights" && (
        <>
          <rect x="36" y="22" width="7" height="50" rx="3" fill={C.navy} />
          <path d="M40 22c0-10 10-14 22-14" stroke={C.navy} strokeWidth="6" fill="none" strokeLinecap="round" />
          <path d="M52 12h20l-4 10H56z" fill={C.navy} />
          <path d="M56 24 50 44h28l-6-20z" fill="#FDE68A" opacity="0.85" />
          <rect x="28" y="68" width="24" height="6" rx="3" fill={C.navy} />
        </>
      )}
      {category === "Pollution" && (
        <>
          <path d="M8 70V42l14 8V42l14 8V30h10v-8h8v48z" fill={C.navy} />
          <circle cx="52" cy="16" r="8" fill="#9CA3AF" /><circle cx="62" cy="12" r="6" fill="#CBD5E1" /><circle cx="70" cy="18" r="5" fill="#E2E8F0" />
          <rect x="14" y="58" width="6" height="6" rx="1" fill={C.saffron} /><rect x="28" y="58" width="6" height="6" rx="1" fill={C.saffron} />
        </>
      )}
      {category === "Other" && (
        <>
          <rect x="12" y="12" width="56" height="56" rx="16" fill={C.navyPale} />
          {[28, 40, 52].map((x) => <circle key={x} cx={x} cy="40" r="5" fill={C.navy} />)}
        </>
      )}
    </svg>
  );
}

/** Empty state: a teammate's service is not connected yet. */
export function PlugArt({ title, ...p }: P) {
  return (
    <svg viewBox="0 0 160 110" {...a11y(title)} {...p}>
      <ellipse cx="80" cy="100" rx="56" ry="6" fill={C.navy} opacity="0.08" />
      <path d="M4 60h40" stroke={C.navySoft} strokeWidth="6" strokeLinecap="round" />
      <rect x="40" y="44" width="30" height="32" rx="8" fill={C.navy} />
      <rect x="70" y="50" width="12" height="5" rx="2" fill={C.navy} /><rect x="70" y="65" width="12" height="5" rx="2" fill={C.navy} />
      <rect x="98" y="44" width="30" height="32" rx="8" fill={C.saffron} />
      <rect x="92" y="50" width="8" height="5" rx="2" fill={C.navySoft} /><rect x="92" y="65" width="8" height="5" rx="2" fill={C.navySoft} />
      <path d="M128 60h28" stroke={C.saffronSoft} strokeWidth="6" strokeLinecap="round" />
      <path d="M84 30l4 8m6-10-2 9m-14-4 6 6" stroke={C.saffron} strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

/** Schemes page hero: a reader with a scroll and translated bubbles. */
export function SchemesArt({ title, ...p }: P) {
  return (
    <svg viewBox="0 0 320 240" {...a11y(title)} {...p}>
      <defs><linearGradient id="scheme-guide" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#EEF2FB" /><stop offset="1" stopColor="#E6F5E2" /></linearGradient><filter id="scheme-shadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="7" stdDeviation="7" floodColor={C.navy} floodOpacity=".14" /></filter></defs>
      <rect x="12" y="12" width="296" height="216" rx="30" fill="url(#scheme-guide)" />
      <path d="M26 183c34-26 65-18 96-3s80 17 172-15v63H26z" fill={C.white} opacity=".78" />
      <g filter="url(#scheme-shadow)"><rect x="36" y="48" width="112" height="132" rx="20" fill={C.white} /><rect x="36" y="48" width="112" height="30" rx="20" fill={C.navy} /><rect x="36" y="64" width="112" height="14" fill={C.navy} /><circle cx="55" cy="63" r="4" fill={C.saffron} /><rect x="67" y="58" width="56" height="9" rx="4.5" fill={C.white} opacity=".85" />{[94, 115, 136].map((y, index) => <g key={y}><circle cx="56" cy={y + 5} r="7" fill={index === 1 ? C.saffronPale : C.leafPale} /><path d={`M53 ${y + 5}l3 3 6-7`} stroke={index === 1 ? C.saffron : C.leaf} strokeWidth="2.3" fill="none" strokeLinecap="round" strokeLinejoin="round" /><rect x="70" y={y} width={index === 2 ? 54 : 64} height="10" rx="5" fill={C.navySoft} /></g>)}</g>
      <g transform="translate(164 48)"><circle cx="46" cy="36" r="29" fill={C.skinLight} /><path d="M18 34c1-28 20-42 37-40 19 2 31 18 25 43-10-11-30-14-47-3-5 3-10 7-15 12z" fill={C.hair} /><circle cx="36" cy="38" r="2.5" fill={C.hair} /><circle cx="56" cy="38" r="2.5" fill={C.hair} /><path d="M39 52q7 5 14 0" stroke={C.hair} strokeWidth="2.5" fill="none" strokeLinecap="round" /><path d="M26 68h39v18H26z" fill={C.skinLight} /><path d="M13 85q33-17 66 0l10 72H4z" fill={C.leaf} /><path d="M17 87 80 150" stroke={C.saffronPale} strokeWidth="8" opacity=".9" /><path d="M17 100q-15 16-10 37" stroke={C.skinLight} strokeWidth="13" fill="none" strokeLinecap="round" /><path d="M78 100q17 10 26 19" stroke={C.skinLight} strokeWidth="13" fill="none" strokeLinecap="round" /><rect x="94" y="104" width="28" height="44" rx="6" fill={C.navy} transform="rotate(13 108 126)" /><rect x="99" y="110" width="18" height="25" rx="3" fill={C.white} transform="rotate(13 108 126)" /><path d="M102 119h12m-10 6h10" stroke={C.leaf} strokeWidth="2" transform="rotate(13 108 126)" /></g>
      <g filter="url(#scheme-shadow)" transform="translate(214 151)"><rect width="72" height="37" rx="14" fill={C.saffron} /><path d="M16 18h23m-23 7h16" stroke={C.white} strokeWidth="3" strokeLinecap="round" /><circle cx="56" cy="19" r="9" fill={C.white} /><path d="M52 19l3 3 5-6" stroke={C.leaf} strokeWidth="2.5" fill="none" strokeLinecap="round" strokeLinejoin="round" /></g>
      <g transform="translate(181 22)"><rect width="95" height="29" rx="14" fill={C.navy} /><text x="47" y="20" textAnchor="middle" fontSize="12" fontWeight="700" fill={C.white} fontFamily="Mukta, sans-serif">Ask · Check · Apply</text></g>
    </svg>
  );
}

/** Grievance page hero: a street with a pothole, a citizen photographing it, a map pin. */
export function StreetArt({ title, ...p }: P) {
  return (
    <svg viewBox="0 0 340 240" {...a11y(title)} {...p}>
      <rect x="0" y="0" width="340" height="240" rx="28" fill={C.saffronPale} />
      <rect x="22" y="70" width="60" height="110" rx="6" fill={C.navySoft} />
      <rect x="92" y="40" width="70" height="140" rx="6" fill="#C9D4EF" />
      <rect x="250" y="56" width="70" height="124" rx="6" fill={C.navySoft} />
      {[0, 1, 2, 3].map((r) => [0, 1].map((c) => <rect key={`${r}${c}`} x={104 + c * 26} y={56 + r * 28} width="18" height="16" rx="3" fill={C.white} opacity="0.85" />))}
      <path d="M0 180h340v60H0z" fill="#8F99AE" />
      <path d="M0 210h340" stroke={C.white} strokeWidth="4" strokeDasharray="22 16" />
      <ellipse cx="200" cy="200" rx="34" ry="9" fill="#3E4659" />
      <path d="M178 196l10-4 8 6 10-5 12 4" stroke="#262C3A" strokeWidth="2.5" fill="none" />
      <rect x="54" y="132" width="14" height="50" rx="6" fill={C.navy} /><rect x="72" y="132" width="14" height="50" rx="6" fill={C.navy} />
      <path d="M48 84q22-10 44 0l6 54q-28 10-56 0z" fill={C.saffron} />
      <circle cx="70" cy="62" r="18" fill={C.skin} />
      <path d="M52 60c1-14 11-20 21-19 10 1 16 9 14 20-4-7-12-10-21-9-6 1-10 4-14 8z" fill={C.hair} />
      <path d="M90 92q18 8 30 6" stroke={C.skin} strokeWidth="11" strokeLinecap="round" fill="none" />
      <rect x="118" y="84" width="22" height="34" rx="5" fill={C.navy} transform="rotate(12 129 101)" />
      <path d="M140 102 182 190" stroke={C.saffron} strokeWidth="2" strokeDasharray="5 5" opacity="0.8" />
      <path d="M282 112c-13 0-23 10-23 23 0 17 23 39 23 39s23-22 23-39c0-13-10-23-23-23z" fill={C.leaf} />
      <circle cx="282" cy="135" r="8" fill={C.white} />
    </svg>
  );
}
