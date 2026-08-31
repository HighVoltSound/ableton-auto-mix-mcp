# Domain Model — Stereo Eblet 3D

## Core Concepts

### Binaural Spatializer
A VST3/CLAP audio plugin that positions mono/stereo sources in 3D space around a listener's head using HRTF (Head-Related Transfer Function) processing. The user places one instance per track in a DAW and positions the sound source on an interactive 3D dome.

### Sound Source (Orb)
The draggable point representing where a sound originates. Positioned on the dome surface by two angular coordinates (Azimuth, Elevation) and one radial coordinate (Distance). Visualized as a glowing coral sphere with concentric emission waves.

### Listener Head
The central reference point. HRTF filters are computed relative to the listener's ear positions. The head model is rendered as a low-poly OBJ mesh with Fresnel glass shader under a transparent dome.

### HRTF Position Index (Head Trajectory)
Parameter controlling which point along the head's vertical axis serves as the HRTF reference. Range: 0.0 (Neck — horizontal-dominant ITD/ILD) to 1.0 (Crown — elevated pinna coloration + crown resonance at 8.5–12 kHz). Automatically bound to the Orb's Elevation — higher source = more crown-level filtering.

### Dome
Transparent hemispherical cage over the listener head. Displays latitude-line markings (+10° to +90°) and concentric distance rings on the floor plane. Rendered via wgpu with Fresnel transparency shader.

### Distance
Physical distance from listener to sound source. Range: 0.3m (close) to 3.0m (far). Visualized as concentric perspective rings on the floor. Scaled logarithmically in Radar view because psychoacoustic differences matter more at close range (0.3–1.0m) than far range (1.0–3.0m).

### Room Model
Discrete early-reflections simulation. Five presets: Dry, Booth, Studio, Club, Cathedral. Controls reverb character and density.

### Mono-Maker
Bass mono crossover at 120 Hz. When enabled, all frequencies below 120 Hz are summed to mono before spatial processing. Prevents phase issues in low-frequency content.

## Views (Synchronized)

All three views read from a single `OrbPosition { azimuth, elevation, distance }` state struct. Only the actively-dragged view writes to state.

### Main 3D Canvas
Center panel (55% width). Shows head model under dome, orb on dome surface, beam to nearest ear, distance rings on floor, latitude markings. Supports free camera rotation (orbit controls).

### Radar Top View
Top-right panel. Bird's-eye view: head at center, concentric distance rings, degree markings (0°–360°). Orb rendered as synchronized dot. Drag adjusts Azimuth + Distance.

### Side Elevation View
Bottom-right panel. Abstract head silhouette in profile, vertical scale -45° to +90°. Orb rendered as synchronized dot. Drag adjusts Elevation.

## UI Widgets

| Widget | Type | Behavior |
|--------|------|----------|
| Knobs (Azimuth, Elevation, Room Amount, Dry/Wet) | Classic round with neon ring indicator | Drag to rotate |
| Room Model | Segmented control (5 buttons) | Dry / Booth / Studio / Club / Cathedral |
| Mono-Maker | LED indicator circle | Glows when active |
| A/B Compare | Two-slot toggle | Switches between two parameter states |
| Preset Browser | ◄ ► buttons | Cycles through 8 instrument presets |
| Preset Bar | 8 instrument buttons | Click = instant parameter set |

## Presets

8 instrument-specific parameter sets: Kick, Snare, HiHats, Bass, Vocal, Lead, Pads, FX. Each defines: Head Trajectory, Azimuth, Elevation, Distance, Bass Mono, Room Model, Room Amount, Dry/Wet.

## Animation Conventions

- Orb-to-ear beam: thicker when dragging orb
- Preset transitions: 300ms ease-in-out animation
- Decorative dust particles: ambient, non-reactive
- Sound waves: concentric semicircles emanating from orb toward head

## Color Palette

Electric Teal + Coral (2026 Trend):
- Background: Deep Indigo-Black `#0a0a1a`
- Dome/Grid: Electric Teal-Cyan `#0ff0fc`
- Orb: Warm Coral-Amber `#ff6b35`
- Head (glass): Translucent Teal `rgba(15,240,252,0.15)`
- Accents: Cool Violet `#7c3aed`
- Text: White `#ffffff` / `rgba(255,255,255,0.5)`
- Active button: Coral gradient `linear-gradient(#ff6b35, #ff2d78)`
