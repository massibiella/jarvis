// Shared type/data contracts used across components — kept separate so
// components/Orb.tsx and components/MindMap.tsx don't need to import from
// each other or from App.tsx.

export type AssistantState = "idle" | "listening" | "thinking" | "speaking";

// ---------------------------------------------------------------------------
// Neural-map placeholder data: mirrors the memory layout planned in the
// backend scaffolding (users/<user_id>/{facts.md,preferences.md,sessions/})
// so this becomes a real, populated graph once the memory API exists — each
// leaf is meant to eventually be one MemoryStore entry, and each branch
// grows its own children as the user talks to Jarvis over time.
// ---------------------------------------------------------------------------
export interface MindMapNode {
  id: string;
  label: string;
  children?: MindMapNode[];
}

export const mindMapData: MindMapNode = {
  id: "jarvis",
  label: "JARVIS",
  children: [
    { id: "facts", label: "Facts", children: [] },
    { id: "preferences", label: "Preferences", children: [] },
    { id: "sessions", label: "Sessions", children: [] },
  ],
};
