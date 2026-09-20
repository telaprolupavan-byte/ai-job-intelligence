import Image from "next/image";

/**
 * The "Job Intelligence" (Page 4) scene — the approved reference
 * artwork (NERO flying, the four data streams, the "Let me connect
 * the dots" bubble, and the "A Clearer Understanding" crystal, all
 * set against the canyon/city environment) reproduced exactly rather
 * than re-approximated in CSS. Cropped tight to the artwork only —
 * the input panels, headline, and copy around it stay real HTML.
 */
export default function NeroJobIntelligenceVisual() {
  return (
    <div className="relative mx-auto w-full max-w-[760px]">
      <Image
        src="/brand/nero-page4-scene.png"
        alt="NERO flying and connecting four glowing data streams — from a Job Description, Resume, Skills, and Preferences panel — into a single glowing crystal labeled 'A Clearer Understanding', saying 'Let me connect the dots.'"
        width={734}
        height={645}
        sizes="(min-width: 1024px) 620px, (min-width: 640px) 560px, 92vw"
        quality={95}
        priority={false}
        className="job-intel-scene-fade nero-float relative z-10 h-auto w-full"
      />
    </div>
  );
}
