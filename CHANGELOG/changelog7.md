# Changelog 7: Teo Group Chat Edition Specification

### Added & Refined
- **Updated `CONTEXT/TEO_SOUL.md` for Group Chat Dynamics**:
  - Engineered Teo specifically for a shared group chat alongside Cache Cappy (9B) and Victor (Human Steering).
  - Enforced the "Context Window Shield" rule: Teo strictly limits output tokens to keep Cache Cappy's 9B KV cache clean and uncluttered.
  - Established conversational protocol: Teo never engages in chit-chat or debate, yields the floor to Capy for architecture, and responds strictly with structured telemetry badges (`⚡ [TEO REPORT]`).
  - Defined explicit group chat trigger commands (`@Teo run tests`, `@Teo check crawler`, `@Teo check disk`, `@Teo test query <text>`).
