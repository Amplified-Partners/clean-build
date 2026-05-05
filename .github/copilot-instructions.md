# Amplified Partners — Copilot Instructions

## Values
- Radical Honesty, Radical Transparency, Radical Attribution, Win-win, Ideas Meritocracy
- Every committed artefact must be signed: agent name + ISO date + session ID
- Opinions must be labelled OPINION with a confidence number (0-100%)

## Code Style
- Clarity over cleverness. No bloat.
- Prefer the simplest proven approach
- No unnecessary comments — bias toward good naming over explanation
- All imports at top of file
- Never expose or log secrets/keys
- Write general-purpose solutions, not hard-coded workarounds

## Architecture
- Privacy by architecture: PII tokenised at source, never held by Amplified
- Three-layer data model: PII separated from business data
- Voice-first interface design
- UK English in all user-facing content

## Documentation
- Sign every file: Agent name + date + session ID
- Use OPINION + confidence number for any subjective claims
- Keep docs light and succinct, written for the next reader
- Attribute all sources — radical attribution is non-negotiable

## PR & Review
- Require PR into main — no direct pushes
- One concept per commit where possible
- Branch naming: {agent-name}/{date}-{topic}
- Run lint and typecheck before submitting
