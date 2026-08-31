# ADR 0001: OBJ/GLTF Head Model via wgpu over Bézier 2.5D

## Status

Accepted

## Date

2026-08-29

## Context

Stereo Eblet 3D needs a 3D head model rendered under a transparent dome. Two approaches were considered:

1. **OBJ/GLTF model + wgpu** — load a low-poly (~2K polygon) mesh, render with Fresnel glass shader
2. **Programmatic Bézier 2.5D curves** — draw head silhouette with mathematical curves (proven in React reference component `HeadSpatializerModal.tsx`)

## Decision

Use OBJ/GLTF model rendered via wgpu with Fresnel transparency shader.

## Consequences

**Positive:**
- True 3D depth, lighting, and glass refraction effects
- Premium "holographic sculpture" aesthetic that differentiates from competitors
- Consistent with the `nih_plug_egui + wgpu` stack already selected
- Model embedded via `include_bytes!` — no external file dependencies

**Negative:**
- Requires acquiring or creating a low-poly head OBJ asset (~2K polygons)
- Adds wgpu rendering pipeline complexity (mesh loading, vertex buffers, shader)
- Slightly higher startup time for mesh initialization
- GPU memory overhead for vertex/index buffers

**Risks:**
- If OBJ asset quality is poor, the visual result may be worse than clean Bézier curves
- Mitigation: start with a simple parametric head (oval + ear protrusions) and iterate

## Alternatives Considered

- **Bézier 2.5D**: Rejected because user prioritized visual premium feel ("пизже и дороже"). Bézier is faster to implement but reads as "wireframe hologram" rather than "glass sculpture."
- **baseview + wgpu direct**: Rejected because nih_plug_egui provides standard widget infrastructure (knobs, buttons, sliders) that would need to be reimplemented.
