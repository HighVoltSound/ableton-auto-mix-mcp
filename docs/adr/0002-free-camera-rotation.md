# ADR 0002: Free Camera Rotation in Main 3D Canvas

## Status

Accepted

## Date

2026-08-29

## Context

The Main 3D Canvas shows the head model under the dome with the orb. The camera perspective needs to be defined. Options:

1. **Fixed 3/4 view** — camera locked at a single angle, only the orb moves
2. **Free rotation** — user can orbit the camera around the scene (orbit, pan, zoom)
3. **Constrained rotation** — camera follows the orb with limited range

## Decision

Use free camera rotation with orbit controls (rotate, pan, zoom).

## Consequences

**Positive:**
- User can examine the 3D positioning from any angle
- More intuitive for understanding spatial relationships (front/back, above/below)
- Professional feel — standard in 3D audio plugins (e.g., dearVR, IEM Plug-in Suite)
- Enables checking HRTF positioning accuracy from multiple viewpoints

**Negative:**
- Adds orbit control implementation (mouse drag for rotate, right-drag for pan, scroll for zoom)
- Must handle edge cases: gimbal lock, camera getting "lost," reset-to-default
- Slightly more complex interaction model for new users
- Need to ensure camera state persists across parameter changes

**Risks:**
- User may get disoriented if camera is too free
- Mitigation: provide a "Reset View" button (double-click or keyboard shortcut) that snaps back to default 3/4 view

## Alternatives Considered

- **Fixed 3/4 view**: Rejected because user explicitly chose "свободное вращение." Also, fixed view limits ability to verify back-of-head positioning which is critical for binaural accuracy.
- **Constrained rotation**: Rejected because partial freedom creates confusion about what's locked and what's free.
