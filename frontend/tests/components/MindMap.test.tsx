import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MindMap } from "../../src/components/MindMap";
import { mindMapData } from "../../src/types";

describe("MindMap", () => {
  it("renders the canvas and the growth hint for the given tree", () => {
    const { container } = render(<MindMap root={mindMapData} />);
    expect(container.querySelector("canvas")).toBeInTheDocument();
    expect(screen.getByText(/this map grows/i)).toBeInTheDocument();
  });
});
