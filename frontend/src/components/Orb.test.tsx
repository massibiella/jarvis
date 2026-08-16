import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Orb } from "./Orb";
import type { AssistantState } from "../types";

const STATES: AssistantState[] = ["idle", "listening", "thinking", "speaking"];

describe("Orb", () => {
  it("renders a canvas for every assistant state without crashing", () => {
    for (const state of STATES) {
      const { container, unmount } = render(<Orb state={state} />);
      expect(container.querySelector("canvas")).toBeInTheDocument();
      unmount();
    }
  });
});
