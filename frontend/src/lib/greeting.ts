// Startup greeting: picks a time-of-day line for Jarvis to speak once, on
// launch, before the user has said or typed anything. Pure/testable on
// purpose — App.tsx owns *when* to call speak() with this, this module only
// decides *what* to say.

export function getGreeting(date: Date = new Date()): string {
  const hour = date.getHours();
  if (hour < 12) return "Good morning, Sir.";
  if (hour < 17) return "Good afternoon, Sir.";
  return "Good evening, Sir.";
}
