// Runs once before every test file: adds jest-dom's DOM matchers
// (toBeInTheDocument, toBeDisabled, ...) to vitest's `expect`, and unmounts
// whatever a test rendered so effects/timers don't leak into the next test.
import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(cleanup);

// Note: jsdom has no canvas backend, so every Orb/MindMap render logs a
// "Not implemented: HTMLCanvasElement's getContext()" warning to the
// console. That's expected and harmless — both components already handle a
// null 2D context gracefully (they just skip drawing) — not a real error.
