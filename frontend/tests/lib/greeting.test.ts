import { describe, expect, it } from "vitest";
import { getGreeting } from "../../src/lib/greeting";

describe("getGreeting", () => {
  it("greets morning before noon", () => {
    expect(getGreeting(new Date(2026, 0, 1, 9))).toBe("Good morning, Sir.");
  });

  it("greets afternoon from noon up to 5pm", () => {
    expect(getGreeting(new Date(2026, 0, 1, 12))).toBe("Good afternoon, Sir.");
    expect(getGreeting(new Date(2026, 0, 1, 16, 59))).toBe("Good afternoon, Sir.");
  });

  it("greets evening from 5pm to just before midnight", () => {
    expect(getGreeting(new Date(2026, 0, 1, 17))).toBe("Good evening, Sir.");
    expect(getGreeting(new Date(2026, 0, 1, 23))).toBe("Good evening, Sir.");
  });

  it("greets morning again right after midnight", () => {
    expect(getGreeting(new Date(2026, 0, 1, 0))).toBe("Good morning, Sir.");
  });
});
