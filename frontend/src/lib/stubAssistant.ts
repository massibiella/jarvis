/**
 * Placeholder responder for the HUD prototype. The real agent core (LLM-agnostic
 * orchestration, tool calls, memory — PRD §4.12/§6) lives in a separate piece of
 * work; this just closes the loop so the voice pipeline and Orb can be demoed
 * end-to-end before that backend exists.
 */
export async function getStubResponse(userText: string): Promise<string> {
  await new Promise((resolve) => setTimeout(resolve, 500));

  const text = userText.toLowerCase();
  if (!text.trim()) {
    return "I didn't catch that. Could you say it again?";
  }
  if (text.includes("hello") || text.includes("hi jarvis")) {
    return "Hello. I'm online, though I'm still just a prototype interface for now.";
  }
  if (text.includes("weather")) {
    return "Weather lookups aren't wired up yet — that's coming once the agent core is connected.";
  }
  if (text.includes("who are you") || text.includes("what are you")) {
    return "I'm Jarvis, a work in progress. Right now I'm only a front-end and voice demo.";
  }
  return `You said: "${userText}". I heard you, but I'm not connected to a reasoning engine yet.`;
}
