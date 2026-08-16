export interface MindMapNode {
  id: string;
  label: string;
  children?: MindMapNode[];
}

/**
 * Placeholder shape for Jarvis's per-user memory map. Deliberately mirrors
 * the memory layout planned in the backend scaffolding branch
 * (users/<user_id>/{facts.md,preferences.md,sessions/}) so this becomes a
 * real, populated graph once the memory API exists — each leaf here is
 * meant to eventually be one MemoryStore entry, and each branch will grow
 * its own children as the user talks to Jarvis over time. Every user's
 * tree is distinct because it's built from their own memory store.
 */
export function getMindMapData(): MindMapNode {
  return {
    id: "jarvis",
    label: "JARVIS",
    children: [
      { id: "facts", label: "Facts", children: [] },
      { id: "preferences", label: "Preferences", children: [] },
      { id: "sessions", label: "Sessions", children: [] },
    ],
  };
}
