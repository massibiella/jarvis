# Jarvis — Product Requirements Document

**Version:** 1.0
**Status:** Draft for review
**Last updated:** 2026-08-16

---

## 1. Overview

Jarvis is a personal, agentic AI assistant modeled conceptually on Iron Man's JARVIS: a persistent, proactive system that manages a user's calendar, investments, information intake, and daily rhythm, and that remembers who each user is across sessions. Unlike a stateless chatbot, Jarvis is expected to take initiative — surfacing what matters at the start and end of each day, holding its own reminders, and acting on the user's behalf within defined boundaries — while remaining portable across underlying LLM providers.

This document defines the full intended scope of Jarvis v1 based on the original feature list and expands each item into concrete, buildable requirements. It is a product-level specification; it intentionally avoids locking in implementation details (specific frameworks, databases, cloud providers) except where a requirement mandates a property (e.g., "LLM-agnostic") that constrains architecture.

## 2. Vision & Goals

- **Vision:** A single trusted assistant that reduces the daily cognitive overhead of managing a schedule, a portfolio, and a stream of information, by acting proactively and remembering context the way a long-term human assistant would.
- **Primary goals:**
  1. Reduce time spent manually checking calendars, portfolios, news, and weather across separate apps.
  2. Give the user a reliable daily rhythm: a morning briefing and an evening wrap-up, without being asked.
  3. Make Jarvis's "memory" durable and personal — it should get more useful over time, not reset per session.
  4. Keep the system provider-neutral so it is not locked to one LLM vendor's pricing, availability, or capabilities.
  5. Support more than one user/household member with isolated identities and preferences.
- **Non-goals (v1):**
  - Replacing the calendar or brokerage as the system of record — Jarvis integrates with and acts on Google/Apple Calendar and IBKR, it does not replace them.
  - General-purpose chatbot / open-domain entertainment use case.
  - Financial advice or automated trading. Investment support is read/monitor/alert-oriented unless explicitly extended later.
  - Full home-automation / IoT control (may be a future extension, not in this version).

## 3. Target Users & Personas

- **Primary user:** The project owner — a technically capable individual who wants a single assistant across calendar, investing, and daily-information needs, and is comfortable configuring self-hosted or cloud-hosted infrastructure.
- **Secondary users:** Additional household/family members or trusted collaborators, each with their own login, calendar accounts, and preferences, isolated from each other's data.
- **Trust model:** All users are assumed authenticated and semi-trusted (e.g., family members), but data must still be partitioned per-user by default — one user should not see another's calendar, portfolio, or memory unless explicitly shared.

## 4. Functional Requirements

Each area below lists the requirement, its scope, and acceptance criteria. Numbering matches functional domains, not the original PRD's flat list.

### 4.1 Calendar Integration
**Requirement:** Jarvis must integrate with Google Calendar and Apple Calendar.

- View events across one or more connected calendars per user.
- Create new events (title, time, location, attendees, notes) via natural-language or structured request.
- Update existing events (reschedule, rename, change attendees/location).
- Delete/cancel events, with confirmation before destructive action.
- Set reminders on calendar events and surface them proactively.
- Reorganize: detect conflicts/overlaps and propose or perform rescheduling when asked.

**Acceptance criteria:**
- A user can say "move my 3pm to 4pm tomorrow" and the correct event is updated on the correct connected calendar.
- Calendar writes are confirmed back to the user (what changed, where) before or immediately after execution.
- Destructive actions (delete) require explicit confirmation unless the user has pre-authorized auto-execution for that action type.
- OAuth tokens for Google/Apple are stored per-user, scoped minimally, and refreshed without requiring re-login on every session.

### 4.2 Investment Portal (IBKR)
**Requirement:** Jarvis must support monitoring and reporting on investments through Interactive Brokers (IBKR).

- Retrieve account balances, positions, and recent trades.
- Retrieve price snapshots and history for holdings and watchlisted symbols.
- Support alerts (price/threshold-based) surfaced proactively, not just on request.
- Include portfolio status in the daily check-ins (§4.9).
- Read-only / monitoring scope for v1 — no order placement or trade execution without a future, explicitly scoped extension.

**Acceptance criteria:**
- A user can ask "how's my portfolio doing" and get current balances/positions/day change.
- Configured alerts (e.g., "notify me if AAPL drops 5%") fire without the user polling for them.
- IBKR credentials/tokens are isolated per user and never shared across accounts.

### 4.3 Newsletter / Content Digests
**Requirement:** Jarvis must support curated updates for investing topics and other user-defined categories of interest.

- Users can define categories of interest (e.g., "AI industry news," "macro markets," a specific sector).
- Jarvis aggregates relevant updates per category on a schedule (e.g., daily) or on demand.
- Investment-related digest content is cross-referenced with the user's actual holdings/watchlist where relevant.
- Digest content is summarized, not just linked — the user should get value without leaving Jarvis.

**Acceptance criteria:**
- Each user can add/remove/edit their categories of interest independently.
- The morning check-in (§4.9) includes a digest section pulling from these categories.

### 4.4 Memory System
**Requirement:** Jarvis must support persistent memory files that carry context across sessions.

- Memory is per-user and includes at minimum: preferences, recurring context (e.g., recurring commitments, known constraints), and relevant history from past interactions.
- Memory must be readable/auditable by the user (the user can see and edit what Jarvis "knows" about them) and correctable/deletable on request.
- Memory is used to personalize check-ins, scheduling suggestions, and digest curation — not stored inertly.
- Memory must be scoped so one user's memory is never exposed to another user.

**Acceptance criteria:**
- Preferences stated once (e.g., "I don't like meetings before 9am") persist and are honored in future scheduling without being restated.
- A user can view and delete their stored memory.

### 4.5 Frontend / User Interface
**Requirement:** Jarvis must have a frontend with visual likeness to Iron Man's JARVIS.

- A HUD-style interface: dark theme, minimalist data-forward layout, ambient status indicators (e.g., voice/listening state, active tasks), and a conversational surface as the primary interaction mode.
- Displays live/near-live status: today's schedule at a glance, portfolio snapshot, weather, pending reminders.
- Must support voice interaction as a first-class input/output mode: the user can speak to Jarvis and receive spoken responses, in addition to text/chat. Voice is not deferrable — it is core to the JARVIS-like experience.
- Must be usable per-user (each logged-in user sees their own HUD, not a shared/global one), including per-user voice profile/wake behavior if applicable.

**Acceptance criteria:**
- The interface visually communicates "assistant is thinking / listening / idle" states, synchronized with actual voice-input/output state.
- Core daily info (schedule, portfolio, weather, reminders) is visible without asking — this is a dashboard, not only a chat window.
- A user can complete a full interaction (e.g., ask about today's schedule, create a reminder) using voice alone, with a spoken response.
- Text/chat remains fully functional as an alternative input mode for situations where voice isn't appropriate.

### 4.6 Authentication & Multi-User Support
**Requirement:** Jarvis must support authentication for multiple distinct users, each with remembered preferences.

- Each user has a distinct login/identity.
- Per-user data isolation applies to calendar connections, IBKR credentials, memory, preferences, and digests (§4.1–4.4).
- Session handling must be secure (see §5 Security).
- Preferences (notification style, check-in timing, categories of interest, etc.) are set and remembered per user.

**Acceptance criteria:**
- Two users on the same Jarvis instance cannot see each other's calendar, portfolio, memory, or preferences.
- A returning user's preferences and memory are automatically applied without reconfiguration.

### 4.7 Security
**Requirement:** Jarvis must be secure by design, given it holds calendar, financial, and personal data.

- All third-party credentials (Google/Apple Calendar OAuth, IBKR) stored encrypted at rest, never logged in plaintext.
- All network traffic encrypted in transit (TLS).
- Principle of least privilege for OAuth scopes requested from Google/Apple/IBKR.
- Authentication supports strong session security (see §5 for detail); destructive or financial-adjacent actions require confirmation.
- Full detail in §5 (Non-Functional Requirements — Security).

### 4.8 Weather
**Requirement:** Jarvis must have access to local weather for the user.

- Retrieve current conditions and forecast for the user's configured location(s).
- Location can be manually set per user and optionally auto-detected.
- Weather is surfaced in the morning check-in (§4.9) and available on demand.

**Acceptance criteria:**
- A user can ask "what's the weather" and get current + short forecast for their location.
- Weather appears automatically in the morning check-in without being requested.

### 4.9 Daily Check-Ins
**Requirement:** Jarvis must deliver a morning check-in and an evening check-in.

- **Morning check-in:** delivered proactively at a per-user configured time, including: weather, relevant news/digest items (§4.3), investment/portfolio updates (§4.2), and the day's calendar/appointments (§4.1).
- **Evening check-in:** delivered proactively at a per-user configured time, summarizing what was accomplished during the day and what is being carried over/deferred to the next day.
- Both check-ins should be generated using the user's memory/preferences (§4.4) to prioritize what's shown.
- Delivery channel(s) configurable — at minimum via the frontend (§4.5); see §9 for open question on push/mobile delivery.

**Acceptance criteria:**
- Morning and evening check-in times are configurable per user and check-ins fire automatically at those times.
- Evening check-in content is derived from actual tracked activity/tasks for that day, not generic filler.

### 4.10 Agent-Owned Reminders
**Requirement:** Jarvis must support reminders that exist independently of the user's calendar.

- Users (or Jarvis itself, proactively) can create reminders that are not written to Google/Apple Calendar.
- These reminders are tracked in Jarvis's own store and surfaced at the appropriate time and in check-ins.
- Supports one-off and recurring reminders.

**Acceptance criteria:**
- A reminder created via Jarvis does not appear on the user's external calendar unless the user explicitly asks for it to be added there.
- Reminders fire/surface at the correct configured time.

### 4.11 Web Browsing & Research
**Requirement:** Jarvis must be able to browse the web and perform research on demand.

- Given a research question, Jarvis can search, retrieve, and synthesize information from the web with source attribution.
- Usable ad hoc ("look this up for me") and as a component of the newsletter/digest feature (§4.3).

**Acceptance criteria:**
- Research answers include cited sources.
- Research capability is available as a general on-demand tool, not limited to the digest pipeline.

### 4.12 LLM-Agnostic Core
**Requirement:** Jarvis must work with any LLM provider given a configuration file, not be hard-coded to one vendor.

- The core agent logic (tool-calling, memory, orchestration) must be decoupled from any single LLM vendor's SDK/API specifics.
- Switching the underlying LLM (e.g., between providers, or between models from the same provider) must be a configuration change, not a code change.
- The configuration file defines at minimum: provider, model identifier, credentials reference, and any provider-specific parameters.
- Tool/function-calling definitions must be expressed in a way that maps to each supported provider's tool-use format.

**Acceptance criteria:**
- Changing the active LLM is achievable by editing configuration only.
- At least two distinct LLM providers are demonstrated working against the same Jarvis core during initial implementation, to validate the abstraction.

### 4.13 Commute Time
**Requirement:** Jarvis must be able to tell the user how long their commute is going to be.

- Retrieve a current, traffic-aware travel-time estimate between the user's configured origin (e.g., home) and destination (e.g., work).
- Origin, destination, and preferred travel mode (driving, transit, etc.) are configurable per user.
- Commute time is surfaced in the morning check-in (§4.9) and available on demand.

**Acceptance criteria:**
- A user can ask "how long is my commute" and get a current estimate that reflects live traffic conditions, not a static average.
- Commute time appears automatically in the morning check-in without being requested.

## 5. Non-Functional Requirements

### 5.1 Security & Privacy
- Encryption at rest for all stored credentials, tokens, and personal data; encryption in transit (TLS) everywhere.
- Per-user data isolation is a hard boundary, enforced at the data-access layer, not just the UI.
- Least-privilege OAuth scopes for every third-party integration (Calendar, IBKR).
- Secrets (API keys, OAuth secrets, IBKR credentials) are never committed to source control and are managed via a secrets store or environment configuration excluded from version control.
- Audit logging for sensitive actions (calendar writes/deletes, credential changes) sufficient to answer "what did Jarvis do and when."
- Confirmation required before irreversible actions (deleting calendar events, etc.) unless the user has explicitly pre-authorized automation for that action class.

### 5.2 Reliability & Availability
- Scheduled behaviors (morning/evening check-ins, alerts, reminders) must fire reliably even if the user is not actively interacting with the frontend at that moment — this implies a background scheduler/service component, not a purely request-driven chat model.
- Integration failures (e.g., IBKR or calendar API downtime) must degrade gracefully — a failed section of a check-in should not block delivery of the rest.

### 5.3 Extensibility
- New integrations (additional calendar providers, brokerages, news sources) should be addable without redesigning the core agent loop.
- The LLM-agnostic requirement (§4.12) and a tool/plugin-style architecture for integrations are both extensibility mechanisms and should be designed together.

### 5.4 Performance
- Interactive chat responses should feel conversational (low seconds, not tens of seconds) for non-research queries.
- Scheduled check-ins should complete generation well before their configured delivery time, with margin for slow upstream APIs.

### 5.5 Observability
- Sufficient logging/monitoring to diagnose failed integrations, missed check-ins, or failed reminders.

## 6. System Architecture Principles

(Product-level constraints only — detailed technical design is a separate document.)

- **LLM abstraction layer:** all reasoning/generation calls go through a provider-agnostic interface driven by configuration (§4.12).
- **Tool/integration layer:** each external system (Google Calendar, Apple Calendar, IBKR, weather provider, web search/browsing) is implemented as a discrete tool the agent can invoke, enabling independent development, testing, and future additions.
- **Memory store:** durable, per-user, queryable by the agent at runtime and editable by the user directly (§4.4).
- **Scheduler/background service:** independent of the chat/request loop, responsible for check-ins, reminders, and alerts firing on time (§5.2).
- **Multi-user identity layer:** authentication and per-user data partitioning applied consistently across every integration and the memory store (§4.6).

## 7. Nice-to-Haves (Not in v1 core scope)

- Mobile messaging integration (e.g., Telegram) so Jarvis can reach the user outside the frontend.

## 8. Assumptions & Constraints

- The user has or will obtain the necessary API access/credentials for Google Calendar, Apple Calendar, IBKR, and any weather/news/search providers used.
- IBKR investment support is monitoring/alerting only in v1; no trade execution.
- Initial deployment is assumed single-household/small-group scale, not a multi-tenant SaaS product, though the architecture should not preclude that later.

## 9. Open Questions

- **Delivery channel for check-ins:** frontend-only for v1, or also push/mobile (relates to the Telegram nice-to-have in §7)? Could also be delivered as a spoken check-in given the voice requirement in §4.5.
- **Voice stack:** which speech-to-text/text-to-speech providers/models, and do they need to satisfy the LLM-agnostic principle (§4.12) the same way the core reasoning model does?
- **Hosting model:** self-hosted, cloud-hosted, or hybrid? Affects the secrets-management and scheduler design in §5–6.
- **LLM provider(s) for initial implementation:** which two providers will be used to validate the LLM-agnostic requirement (§4.12)?
- **News/digest sources:** which specific data sources/APIs power §4.3 — TBD, pending selection.

## 10. Glossary

- **Check-in:** the proactive morning/evening summary Jarvis delivers (§4.9).
- **Agent-owned reminder:** a reminder tracked by Jarvis independent of any external calendar (§4.10).
- **LLM-agnostic:** the property that Jarvis's core logic functions with any sufficiently capable LLM, selected via configuration rather than hard-coded integration (§4.12).
