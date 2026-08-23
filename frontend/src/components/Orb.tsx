import { useEffect, useRef } from "react";
import { audioEngine } from "../lib/voice";
import type { AssistantState } from "../types";

interface OrbProps {
  state: AssistantState;
}

// Jarvis's color never changes with state — only the header status text
// does. One palette, always red.
const RED = { core: "#551515", ring: "#ff4d4d", glow: "rgba(255, 77, 77, 0.35)" };

const POINTS = 96;

// The lowest few FFT bins carry bass/DC energy far larger than the rest of
// the spectrum; sampling them at all drags the ring into a lopsided bulge
// right at angle 0. Skip them entirely rather than clamping into them.
const SKIP_BINS = 4;
const WINDOW = 3;

// Human speech puts almost all its energy in the lower ~60% of what's left
// of the spectrum after SKIP_BINS -- a plain linear i-to-bin mapping gives
// the near-silent high end its own full contiguous arc of the ring, which
// reads as visibly "dead" (no spikes at all) next to the rest even once
// blended with the overall level. Instead, only ever sample from that
// livelier low/mid band, and sweep through it several times per lap
// (a triangle wave, so each lobe's edges land on the same value with no
// jump) so every point on the ring -- including what used to be the flat
// top -- gets real, varying energy instead of near-silence.
const ACTIVE_FRACTION = 0.6;
const REPEAT_LOBES = 3;

// REPEAT_LOBES gives the ring 3-fold rotational symmetry (a spike every
// 120°), which by default lands one spike pointing straight up -- reading
// as lopsided rather than balanced. Rotating the whole ring's frame by a
// fixed offset just settles it into a more visually even resting
// orientation; 45° clockwise (eyeballed) is what looks balanced here.
const BASE_ROTATION = Math.PI / 4;

/** Smoothed amplitude (0-1) of the frequency band centered on ring-point i. */
function sampleBand(freq: Uint8Array, i: number): number {
  const usable = freq.length - SKIP_BINS;
  const activeRange = Math.max(1, Math.floor(usable * ACTIVE_FRACTION));

  const cycle = ((i * REPEAT_LOBES) / POINTS) % 1;
  const triangle = cycle < 0.5 ? cycle * 2 : 2 - cycle * 2; // 0 -> 1 -> 0
  const center = Math.floor(triangle * (activeRange - 1));

  let sum = 0;
  for (let k = -WINDOW; k <= WINDOW; k++) {
    const idx = (((center + k) % activeRange) + activeRange) % activeRange;
    sum += freq[SKIP_BINS + idx];
  }
  return sum / (WINDOW * 2 + 1) / 255;
}

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

      // The orb visualizes Jarvis, not the user — it only reacts to real
      // audio while Jarvis is speaking. While listening (the user talking)
      // it behaves exactly like idle; the user's mic level is shown in the
      // header's MicLevelBar instead.
      const s = stateRef.current;
      const anim = s === "listening" ? "idle" : s;

      const w = canvas.width;
      const h = canvas.height;
      const cx = w / 2;
      const cy = h / 2;
      const baseRadius = w * 0.22;

      ctx.clearRect(0, 0, w, h);

      const freq = anim === "speaking" ? audioEngine.getFrequencyData() : null;
      const level = anim === "speaking" ? audioEngine.getLevel() : 0;

      // outer ambient glow
      const glowRadius = baseRadius * (1.8 + level * 0.6);
      const gradient = ctx.createRadialGradient(cx, cy, baseRadius * 0.3, cx, cy, glowRadius);
      gradient.addColorStop(0, RED.glow);
      gradient.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.arc(cx, cy, glowRadius, 0, Math.PI * 2);
      ctx.fill();

      // waveform ring
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(BASE_ROTATION);
      if (anim === "thinking") {
        ctx.rotate(t * 0.6);
      }

      ctx.beginPath();
      for (let i = 0; i <= POINTS; i++) {
        const angle = (i / POINTS) * Math.PI * 2;
        let offset: number;

        if (freq) {
          // Blend this point's own (now always-active, see sampleBand)
          // frequency band with the OVERALL level: the per-band term gives
          // the ring its spiky, organic waveform texture at every point
          // around it, and the level term makes the whole ring visibly
          // expand together as Jarvis's volume rises.
          offset = (sampleBand(freq, i) * 0.4 + level * 0.3) * baseRadius;
        } else if (anim === "thinking") {
          offset = (Math.sin(angle * 4 + t * 3) * 0.5 + 0.5) * baseRadius * 0.35;
        } else {
          // idle (and listening): calm, mostly-circular breathing with a
          // faint traveling ripple — never driven by the user's mic.
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
      ctx.strokeStyle = RED.ring;
      ctx.shadowColor = RED.ring;
      ctx.shadowBlur = w * 0.03;
      ctx.stroke();

      ctx.fillStyle = RED.core;
      ctx.globalAlpha = 0.35;
      ctx.fill();
      ctx.globalAlpha = 1;

      ctx.restore();

      // inner core dot, pulses gently even at idle so the assistant reads as "alive"
      const corePulse =
        1 + Math.sin(t * (anim === "idle" ? 1.4 : 6)) * (anim === "idle" ? 0.06 : 0.02 + level * 0.15);
      ctx.beginPath();
      ctx.fillStyle = RED.ring;
      ctx.shadowColor = RED.ring;
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
