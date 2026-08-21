import { useEffect, useRef } from "react";
import { audioEngine } from "../lib/voice";
import type { AssistantState } from "../types";

interface OrbProps {
  state: AssistantState;
}

const PALETTE: Record<AssistantState, { core: string; ring: string; glow: string }> = {
  idle: { core: "#551515", ring: "#e02c2c", glow: "rgba(224, 44, 44, 0.25)" },
  listening: { core: "#6b1010", ring: "#ff4d4d", glow: "rgba(255, 77, 77, 0.45)" },
  thinking: { core: "#3a2a5c", ring: "#a06bff", glow: "rgba(160, 107, 255, 0.4)" },
  speaking: { core: "#5c3a1a", ring: "#ffd27a", glow: "rgba(255, 210, 122, 0.5)" },
};

const POINTS = 96;

export function Orb({ state }: OrbProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stateRef = useRef(state);
  stateRef.current = state;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let raf = 0;
    let t = 0;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    const resize = () => {
      const parent = canvas.parentElement;
      const size = parent ? Math.min(parent.clientWidth, parent.clientHeight) : 320;
      canvas.width = size * dpr;
      canvas.height = size * dpr;
      canvas.style.width = `${size}px`;
      canvas.style.height = `${size}px`;
    };
    resize();
    const ro = new ResizeObserver(resize);
    if (canvas.parentElement) ro.observe(canvas.parentElement);

    const draw = () => {
      raf = requestAnimationFrame(draw);
      t += 0.016;

      const s = stateRef.current;
      const palette = PALETTE[s];
      const w = canvas.width;
      const h = canvas.height;
      const cx = w / 2;
      const cy = h / 2;
      const baseRadius = w * 0.22;

      ctx.clearRect(0, 0, w, h);

      // amplitude source: real audio during listening/speaking, synthetic otherwise
      const freq = s === "listening" || s === "speaking" ? audioEngine.getFrequencyData() : null;
      const level = s === "listening" || s === "speaking" ? audioEngine.getLevel() : 0;

      // outer ambient glow
      const glowRadius = baseRadius * (1.8 + level * 0.6);
      const gradient = ctx.createRadialGradient(cx, cy, baseRadius * 0.3, cx, cy, glowRadius);
      gradient.addColorStop(0, palette.glow);
      gradient.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.arc(cx, cy, glowRadius, 0, Math.PI * 2);
      ctx.fill();

      // waveform ring
      ctx.save();
      ctx.translate(cx, cy);
      if (s === "thinking") {
        ctx.rotate(t * 0.6);
      }

      ctx.beginPath();
      for (let i = 0; i <= POINTS; i++) {
        const angle = (i / POINTS) * Math.PI * 2;
        let offset: number;

        if (freq) {
          // Average a small window of neighboring bins (skipping the very
          // lowest, which carry bass/DC energy far larger than the rest and
          // otherwise drag the ring into a single lopsided bulge) so the
          // ring reads as a smooth reactive wobble instead of jagged noise.
          const center = Math.floor((i / POINTS) * freq.length);
          const window = 3;
          let sum = 0;
          for (let k = -window; k <= window; k++) {
            const idx = Math.max(4, (center + k + freq.length) % freq.length);
            sum += freq[idx];
          }
          const bin = sum / (window * 2 + 1) / 255;
          offset = bin * baseRadius * 0.5;
        } else if (s === "thinking") {
          offset = (Math.sin(angle * 4 + t * 3) * 0.5 + 0.5) * baseRadius * 0.35;
        } else {
          // idle: calm, mostly-circular breathing with a faint traveling ripple
          offset =
            Math.sin(t * 1.1) * baseRadius * 0.05 + Math.sin(angle * 5 + t * 0.8) * baseRadius * 0.015;
        }

        const r = baseRadius + offset;
        const x = Math.cos(angle) * r;
        const y = Math.sin(angle) * r;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();

      ctx.lineWidth = w * 0.006;
      ctx.strokeStyle = palette.ring;
      ctx.shadowColor = palette.ring;
      ctx.shadowBlur = w * 0.03;
      ctx.stroke();

      ctx.fillStyle = palette.core;
      ctx.globalAlpha = 0.35;
      ctx.fill();
      ctx.globalAlpha = 1;

      ctx.restore();

      // inner core dot, pulses gently even at idle so the assistant reads as "alive"
      const corePulse = 1 + Math.sin(t * (s === "idle" ? 1.4 : 6)) * (s === "idle" ? 0.06 : 0.02 + level * 0.15);
      ctx.beginPath();
      ctx.fillStyle = palette.ring;
      ctx.shadowColor = palette.ring;
      ctx.shadowBlur = w * 0.05;
      ctx.arc(cx, cy, baseRadius * 0.12 * corePulse, 0, Math.PI * 2);
      ctx.fill();
    };

    draw();
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, []);

  return (
    <div className="orb-container">
      <canvas ref={canvasRef} />
    </div>
  );
}
