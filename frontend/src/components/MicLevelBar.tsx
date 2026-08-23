import { useEffect, useRef } from "react";
import { audioEngine } from "../lib/voice";

interface MicLevelBarProps {
  /** Whether the mic is live (AssistantState === "listening"). */
  active: boolean;
}

/**
 * Header-level meter for the USER's mic input. Split out from Orb on
 * purpose — the orb visualizes Jarvis, not the person talking to it, so the
 * user's voice gets its own indicator instead of being forced onto it.
 *
 * Reads audioEngine directly on a rAF loop (not React state) so it doesn't
 * re-render the component tree every frame — same approach as Orb.
 */
export function MicLevelBar({ active }: MicLevelBarProps) {
  const fillRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!active) return;
    const fill = fillRef.current;
    let raf = 0;

    const draw = () => {
      raf = requestAnimationFrame(draw);
      const level = audioEngine.getLevel();
      const pct = Math.min(1, level * 1.6) * 100;
      if (fill) fill.style.width = `${pct}%`;
    };
    draw();

    return () => {
      cancelAnimationFrame(raf);
      if (fill) fill.style.width = "0%";
    };
  }, [active]);

  return (
    <div className={`mic-level-row ${active ? "active" : ""}`}>
      <div className="mic-level-track">
        <div className="mic-level-fill" ref={fillRef} />
      </div>
    </div>
  );
}
