import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MicLevelBar } from "../../src/components/MicLevelBar";

vi.mock("../../src/lib/voice", () => ({
  audioEngine: { getLevel: vi.fn(() => 0.5) },
}));

describe("MicLevelBar", () => {
  it("renders inactive without crashing", () => {
    const { container } = render(<MicLevelBar active={false} />);
    expect(container.querySelector(".mic-level-row")).not.toHaveClass("active");
  });

  it("renders active without crashing", () => {
    const { container } = render(<MicLevelBar active={true} />);
    expect(container.querySelector(".mic-level-row")).toHaveClass("active");
  });
});
