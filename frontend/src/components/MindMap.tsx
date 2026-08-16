import { useEffect, useRef } from "react";
import type { MindMapNode } from "../lib/mindMapData";

interface MindMapProps {
  root: MindMapNode;
}

interface LaidOutNode {
  node: MindMapNode;
  depth: number;
  x: number;
  y: number;
  parent: LaidOutNode | null;
}

function countLeaves(node: MindMapNode): number {
  if (!node.children || node.children.length === 0) return 1;
  return node.children.reduce((sum, child) => sum + countLeaves(child), 0);
}

/**
 * Radial tree layout: root at the center, each subtree gets an angular
 * slice proportional to its leaf count so branches never overlap,
 * regardless of how deep or wide the tree grows.
 */
function layout(
  node: MindMapNode,
  depth: number,
  angleStart: number,
  angleEnd: number,
  radiusStep: number,
  parent: LaidOutNode | null,
  out: LaidOutNode[]
): void {
  const angle = (angleStart + angleEnd) / 2;
  const radius = depth * radiusStep;
  const laid: LaidOutNode = {
    node,
    depth,
    x: Math.cos(angle) * radius,
    y: Math.sin(angle) * radius,
    parent,
  };
  out.push(laid);

  const children = node.children ?? [];
  if (children.length === 0) return;

  const totalLeaves = countLeaves(node);
  let cursor = angleStart;
  for (const child of children) {
    const share = countLeaves(child) / totalLeaves;
    const childEnd = cursor + share * (angleEnd - angleStart);
    layout(child, depth + 1, cursor, childEnd, radiusStep, laid, out);
    cursor = childEnd;
  }
}

// simple string hash so each node gets a stable, distinct animation phase
function phaseFor(id: string): number {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) % 1000;
  return h / 1000;
}

export function MindMap({ root }: MindMapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

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
      const w = parent?.clientWidth ?? 800;
      const h = parent?.clientHeight ?? 600;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
    };
    resize();
    const ro = new ResizeObserver(resize);
    if (canvas.parentElement) ro.observe(canvas.parentElement);

    const nodes: LaidOutNode[] = [];
    layout(root, 0, 0, Math.PI * 2, 1, null, nodes);
    const maxDepth = nodes.reduce((m, n) => Math.max(m, n.depth), 0) || 1;

    const draw = () => {
      raf = requestAnimationFrame(draw);
      t += 0.016;

      const w = canvas.width;
      const h = canvas.height;
      const cx = w / 2;
      const cy = h / 2;
      const radiusStep = (Math.min(w, h) * 0.42) / maxDepth;

      ctx.clearRect(0, 0, w, h);

      // edges
      ctx.lineWidth = w * 0.0015;
      ctx.strokeStyle = "rgba(255, 77, 77, 0.35)";
      for (const n of nodes) {
        if (!n.parent) continue;
        const px = cx + n.parent.x * radiusStep;
        const py = cy + n.parent.y * radiusStep;
        const nx = cx + n.x * radiusStep;
        const ny = cy + n.y * radiusStep;
        ctx.beginPath();
        ctx.moveTo(px, py);
        ctx.lineTo(nx, ny);
        ctx.stroke();
      }

      // nodes
      for (const n of nodes) {
        const x = cx + n.x * radiusStep;
        const y = cy + n.y * radiusStep;
        const phase = phaseFor(n.node.id);
        const pulse = 0.85 + Math.sin(t * 1.2 + phase * Math.PI * 2) * 0.15;
        const baseSize = w * (n.depth === 0 ? 0.014 : 0.008) * (1 - n.depth * 0.08 + 0.08);

        ctx.beginPath();
        ctx.fillStyle = n.depth === 0 ? "#ff4d4d" : "#e02c2c";
        ctx.shadowColor = "#ff4d4d";
        ctx.shadowBlur = w * 0.012 * pulse;
        ctx.arc(x, y, Math.max(baseSize * pulse, 2), 0, Math.PI * 2);
        ctx.fill();

        ctx.shadowBlur = 0;
        ctx.fillStyle = n.depth === 0 ? "#ffb3b3" : "#d99a9a";
        ctx.font = `${n.depth === 0 ? 600 : 400} ${Math.max(w * 0.011, 11)}px Rajdhani, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        ctx.fillText(n.node.label, x, y + baseSize + w * 0.008);
      }
    };

    draw();
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [root]);

  return (
    <div className="mindmap-container">
      <canvas ref={canvasRef} />
      <p className="mindmap-hint">This map grows as Jarvis learns more about you.</p>
    </div>
  );
}
