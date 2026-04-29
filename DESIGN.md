---
name: Nut Counter
description: Industrial kiosk UI for counting fasteners on a factory production line.
colors:
  counting-light: "oklch(0.89 0.19 126)"
  counting-light-pressed: "oklch(0.82 0.18 126)"
  verification-green: "oklch(0.67 0.062 123)"
  factory-beige-light: "oklch(0.96 0.009 85)"
  factory-beige-panel: "oklch(0.91 0.018 85)"
  factory-beige-strong: "oklch(0.86 0.022 84)"
  factory-beige-pressed: "oklch(0.80 0.026 84)"
  factory-beige-shell: "oklch(0.78 0.019 86)"
  machine-seam: "oklch(0.68 0.024 82)"
  dead-label: "oklch(0.44 0.022 78)"
  control-black: "oklch(0.17 0.006 80)"
  display-void: "oklch(0.14 0.006 95)"
  display-void-raised: "oklch(0.18 0.008 95)"
  fault-red: "oklch(0.45 0.14 28)"
  fault-red-strong: "oklch(0.58 0.18 28)"
  fault-red-soft: "oklch(0.88 0.046 33)"
typography:
  display:
    fontFamily: "\"IBM Plex Mono\", \"SFMono-Regular\", Consolas, monospace"
    fontSize: "clamp(5rem, 11vw, 8rem)"
    fontWeight: 600
    lineHeight: 1
    fontFeature: "\"tnum\" 1"
  headline:
    fontFamily: "\"Noto Sans Thai\", system-ui, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 700
    lineHeight: 1.25
  title:
    fontFamily: "\"Noto Sans Thai\", system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "0.1em"
  body:
    fontFamily: "\"Noto Sans Thai\", system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 500
    lineHeight: 1.5
  label:
    fontFamily: "\"Noto Sans Thai\", system-ui, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 600
    letterSpacing: "0.28em"
rounded:
  none: "0"
  micro: "0.15rem"
  sm: "0.25rem"
  lg: "1.25rem"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "20px"
  header: "64px"
  action-bar: "88px"
components:
  button-primary:
    backgroundColor: "{colors.counting-light}"
    textColor: "{colors.control-black}"
    rounded: "{rounded.micro}"
    padding: "10px 20px"
  button-primary-pressed:
    backgroundColor: "{colors.counting-light-pressed}"
    textColor: "{colors.control-black}"
    rounded: "{rounded.micro}"
    padding: "10px 20px"
  button-danger:
    backgroundColor: "{colors.fault-red}"
    textColor: "oklch(0.98 0 0)"
    rounded: "{rounded.lg}"
    padding: "10px 20px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.dead-label}"
    rounded: "{rounded.lg}"
    padding: "10px 20px"
  button-confirm:
    backgroundColor: "{colors.control-black}"
    textColor: "{colors.factory-beige-light}"
    rounded: "{rounded.lg}"
    padding: "10px 20px"
  fastener-selector:
    backgroundColor: "{colors.factory-beige-panel}"
    textColor: "{colors.control-black}"
    rounded: "{rounded.none}"
    padding: "20px 16px"
  fastener-selector-active:
    backgroundColor: "{colors.counting-light}"
    textColor: "{colors.control-black}"
    rounded: "{rounded.none}"
    padding: "20px 16px"
---

# Design System: Nut Counter

## 1. Overview

**Creative North Star: "The Calibrated Scale"**

Nut Counter's interface is built like a precision measurement instrument that happens to run on a touchscreen. Every surface is a readout. Every control is a physical actuator. The machine is always truthful, always exact — no ornamentation survives unless it serves legibility or operation.

The layout is divided by function, not by aesthetics. The warm Factory Beige shell carries the controls: fastener selection on the left, system actions on the right. The center is surrendered entirely to the camera — a Display Void column where the count and feed live in high contrast against near-black. This two-temperature palette (warm beige outside, near-black inside) is structural, not decorative. It separates the operational surface from the measurement surface at a glance, even from across the room.

This system explicitly rejects SaaS dashboard conventions, decorative cyber interfaces, and colorful consumer UI. It is not a mobile app. It is not a product landing page. Tiny touch targets, ornamental motion, unnecessary data panels, and loud saturated color are prohibited. The Counting Light accent appears only to mark what is selected or confirmed — its restraint is the point.

**Key Characteristics:**
- Two thermal zones: warm Factory Beige shell (controls) vs. Display Void center (measurement)
- Single accent color marks selection and the live count; used nowhere else
- Flat, near-zero-radius surfaces on all kiosk controls; softness reserved for consumer-facing dialogs
- IBM Plex Mono for all machine-produced numbers; Noto Sans Thai for all labels and copy
- Motion limited to color-only state transitions, no choreography
- Glove-safe touch targets: minimum 44px height, wide padded columns, 4px inset focus rings

## 2. Colors: The Factory Floor Palette

A two-temperature system: the shell and control panels are warm and beige-adjacent; the measurement center is cold and near-black. One accent bridges both zones.

### Primary
- **Counting Light** (`oklch(0.89 0.19 126)`): The machine's single active-state signal. Appears on the selected fastener button, active operator-panel tabs, and the count numeral on the Display Void. Warm yellow-green — readable against both Factory Beige and Display Void without needing a border. Treat it as a status lamp: on or off, nothing in between.
- **Counting Light Pressed** (`oklch(0.82 0.18 126)`): Depressed state of Counting Light. Used for borders on active tab buttons.

### Secondary
- **Verification Green** (`oklch(0.67 0.062 123)`): Muted green for status labels on the Display Void ("พร้อมนับ", "ผลนับ", "นับได้"). Low chroma so it does not compete with Counting Light. Used only in the display center.

### Neutral
- **Factory Beige Light** (`oklch(0.96 0.009 85)`): Near-white warm surface. Stepper value display cells, light section backgrounds in the operator panel.
- **Factory Beige Panel** (`oklch(0.91 0.018 85)`): Primary panel background. Left selector column, right action column, operator panel body.
- **Factory Beige Strong** (`oklch(0.86 0.022 84)`): Hover state for panel buttons, action bar background.
- **Factory Beige Pressed** (`oklch(0.80 0.026 84)`): Active/pressed state for panel buttons and touch feedback.
- **Factory Beige Shell** (`oklch(0.78 0.019 86)`): Outer machine shell. Page body background, bottom of the background gradient.
- **Machine Seam** (`oklch(0.68 0.024 82)`): All borders and dividers. The visible seam between panels and sections.
- **Dead Label** (`oklch(0.44 0.022 78)`): Secondary text, eyebrow labels, footer status strings, inactive tab icons.
- **Control Black** (`oklch(0.17 0.006 80)`): Primary ink for headings and values. Also used as the confirm/save button fill on beige surfaces.
- **Display Void** (`oklch(0.14 0.006 95)`): The near-black measurement column. Camera feed background, count display background. Slight blue-gray cast distinguishes it from a chromatic black and reduces apparent glare on bright-lit screens.
- **Display Void Raised** (`oklch(0.18 0.008 95)`): Lifted surface within the display zone.

### Danger
- **Fault Red** (`oklch(0.45 0.14 28)`): Error fill for the display panel and fault icon tint. Warm burnt red-orange — not a pure red, which would read as alarm rather than machine fault.
- **Fault Red Strong** (`oklch(0.58 0.18 28)`): Brighter fault tint for icons in high-contrast contexts.
- **Fault Red Soft** (`oklch(0.88 0.046 33)`): Pale tint for inline error alert backgrounds.

### Named Rules
**The One Lamp Rule.** Counting Light is used on exactly two things: the active selection indicator and the live count numeral. It is never used decoratively, as a background fill on non-interactive surfaces, or as a text highlight. Its scarcity is what makes it legible from across the machine.

**The Two-Temperature Rule.** Factory Beige and Display Void are complementary zones, not competing styles. Never apply Display Void to shell or panel surfaces. Never apply Factory Beige to the display center column. The boundary between them is absolute.

## 3. Typography

**Display Font:** IBM Plex Mono (with SFMono-Regular, Consolas, monospace fallback)
**UI Font:** Noto Sans Thai (with system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif fallback)

**Character:** IBM Plex Mono carries every number the machine produces or consumes: counts, GPIO pin values, config measurements. Its tabular numerals (`font-feature-settings: "tnum" 1`) prevent layout shift as digits change under live polling. Noto Sans Thai handles all labels, headings, and body copy — chosen for legibility with Thai script at small sizes in bright reflective environments. The pairing is functional, not aspirational: a measurement instrument and its callouts.

### Hierarchy
- **Display** (IBM Plex Mono, weight 600, `clamp(5rem, 11vw, 8rem)`, line-height 1): The count numeral. The single most visible element on screen. Always in Counting Light on Display Void. `font-feature-settings: "tnum" 1`. Never used outside the count display column.
- **Headline** (Noto Sans Thai, weight 700, 1.25rem/20px, line-height 1.25): Panel headings, dialog titles, section headers in the operator panel.
- **Title** (Noto Sans Thai, weight 600, 1.125rem/18px, tracking 0.1em, uppercase): Display panel state labels ("นับได้", "พร้อมนับ"). Carries semantic state alongside the count numeral.
- **Body** (Noto Sans Thai, weight 500, 0.9375rem/15px, line-height 1.5): Operator panel copy, dialog messages, config labels.
- **Label** (Noto Sans Thai, weight 600, 0.6875rem/11px, tracking 0.28em, uppercase): Section eyebrows ("operator", "power", "ชนิดชิ้นงาน", "ผลนับ"). Dead Label color. Wide letter-spacing for legibility at small size.
- **Mono Value** (IBM Plex Mono, weight 700, 1rem/16px): Inline config values, GPIO numbers, stepper displays. Not a heading level — always inline within a labeled field.

### Named Rules
**The Mono-for-Machines Rule.** IBM Plex Mono is reserved for numbers the machine produces or the operator configures. It never appears in headings, body copy, or navigation labels. The distinction is strict: if it is a human word, it is Thai sans; if it is a machine number, it is mono.

## 4. Elevation

This system is flat by default. The kiosk surface has no ambient shadows, no tonal elevation between the shell panels — the Machine Seam border and the background color step between zones carry all the depth information an operator needs.

Floating surfaces (operator panel overlay, confirmation dialogs) use a dark scrim plus Tailwind `shadow-2xl` exclusively. The operator panel scrim is `oklch(0.14 0.006 95 / 0.76)` — darker, since the operator panel occupies the full screen. Dialog scrims use `rgba(0,0,0,0.60)` with `backdrop-filter: blur(4px)`.

### Shadow Vocabulary
- **Overlay shadow** (`0 25px 50px -12px rgba(0,0,0,0.25)` — Tailwind shadow-2xl): Used only on floating overlays: the operator panel and confirmation dialogs. Signals that the surface has lifted above the kiosk plane.

### Named Rules
**The Flat-by-Default Rule.** Kiosk panels are flat at rest. No shadow appears between the shell, selector column, or display center. Depth is expressed through color temperature difference (warm vs. void) and the Machine Seam border — not through shadows. The only shadows in the system are on surfaces that float above the kiosk.

## 5. Components

### Fastener Selector Buttons
The primary kiosk interaction. Full-height grid cells with no border radius; the buttons fill the entire left column and extend to every edge.
- **Shape:** No radius (0). These are not cards or affordances — they are panels within the machine housing.
- **Default:** Factory Beige Panel background, Control Black text, Machine Seam bottom border. Product image at 85% opacity with `mix-blend-multiply` to blend the white product photo background into the beige panel.
- **Active (aria-pressed):** Counting Light background, product image at 100% opacity (no blend mode, image appears on green), Control Black text.
- **Hover:** Factory Beige Strong background.
- **Pressed:** Factory Beige Pressed background.
- **Focus visible:** 4px inset Counting Light ring (`focus-visible:ring-4 focus-visible:ring-inset`).
- **Transition:** `transition-colors duration-150` — immediate feedback.

### Count Display Panel
The right column's primary content. The machine's measurement output surface.
- **Background states:** Display Void in waiting and complete states; Fault Red in error state. The full-panel color shift is intentional — error state must interrupt at a glance, not annotate.
- **Count numeral:** IBM Plex Mono, `clamp(5rem, 11vw, 8rem)`, Counting Light, tabular numerals, `aria-live="polite"`.
- **Waiting state text ("วางถาด"):** Noto Sans Thai, weight 900, `clamp(3rem, 5.5vw, 4.6rem)`, line-height 0.95, Counting Light.
- **Error state text ("ตรวจเครื่อง"):** Noto Sans Thai, weight 900, `clamp(2rem, 4.2vw, 3.25rem)`, Factory Beige Light.
- **Status labels:** 18px semibold uppercase, Verification Green on Display Void; Fault Red Soft on error background.

### Control Footer
The two-button strip at the base of the right column. Settings and power.
- **Shape:** No radius. Factory Beige Strong background, Machine Seam top border and internal divider. Height 88px (5.5rem) for glove-safe tapping.
- **Icons:** 24×24px Lucide. Power icon is always Fault Red — a persistent danger signal independent of machine state. Settings icon is Control Black.
- **Hover/active:** Factory Beige Pressed background, `transition-colors duration-100`.
- **Focus visible:** 4px inset Counting Light ring.

### Operator Panel
Full-screen configuration overlay, not part of the normal count cycle. Accessed via the Settings button.
- **Container:** Max-width 5xl, Factory Beige Panel background, 2px Machine Seam border, 0.25rem corner radius (4px), shadow-2xl.
- **Sidebar (w-52):** Background `#e6dfd2` (slightly deeper warm beige). Contains 48px tab buttons with 0.2rem radius.
- **Tab button active:** Counting Light background, Counting Light Pressed border.
- **Tab button inactive:** No border, Dead Label text, hover: Machine Seam border + Factory Beige Strong background.
- **Header + footer:** Machine Seam border, 64px height.
- **Save button (primary action):** Control Black background, Factory Beige Light text, 0.2rem radius.
- **Utility icon buttons (refresh, close):** Factory Beige Strong background, Machine Seam border, 44×44px, 0.2rem radius.

### Stepper Field
Glove-safe numeric incrementer for config values.
- **Layout:** Five-column grid `[1fr 1fr 1.4fr 1fr 1fr]`. The center cell is a read-only value display; flanking pairs decrement/increment by small step and large step.
- **Increment/decrement buttons:** 44px height, 0.15rem radius, Machine Seam border, Factory Beige Panel background. IBM Plex Mono weight 900. Hover: Factory Beige Strong. Active: Factory Beige Pressed.
- **Value cell:** 44px height, Factory Beige Light background, Machine Seam border, IBM Plex Mono weight 900, Control Black.

### Toggle Field
Boolean option row used in operator panel config.
- **Layout:** Full-width label row, space-between, 0.15rem radius, Machine Seam border, Factory Beige Strong background.
- **Checkbox:** 20×20px, `accent-color: oklch(0.89 0.19 126)` (Counting Light).

### Confirmation Dialogs
Shutdown confirmation and password prompt. The only surfaces in the system with 1.25rem (20px) corner radius.
- **Rationale:** The rounded corner is a deliberate softness signal. It tells the operator this interaction requires attention and decision — not reflex. The roundness is the affordance.
- **Container:** max-width sm (384px), Factory Beige Panel background, Machine Seam border, shadow-2xl, 20px radius.
- **Header row:** Machine Seam bottom border, danger color on hazard icon, eyebrow label in Dead Label + headline in Control Black.
- **Danger action button:** Fault Red background, white text, 1rem radius (rounded-2xl).
- **Cancel button:** No background, Dead Label text, 1rem radius, `hover:bg-black/5`.
- **Submit/confirm button:** Control Black background, white text, 1rem radius.

### Inline Alerts
- **Error:** Fault Red Soft background (`oklch(0.88 0.046 33)`), border `#dfc0b6`, Fault Red text. 0.2rem radius in operator panel.
- **Success:** `#edf7df` background, `#bfd49b` border, `#476119` text. 0.2rem radius in operator panel.

### Camera Feed
Full-height, full-width `object-cover`, mirrored horizontally with `-scale-x-100`. Display Void background. On load state: centered spinning loader in Verification Green. On error state: TriangleAlert icon in Fault Red Strong. Both overlay states maintain a centered label in Display Label color.

## 6. Do's and Don'ts

### Do:
- **Do** use Counting Light only on the active selection state and the live count numeral. Its rarity is its legibility.
- **Do** use IBM Plex Mono with `font-feature-settings: "tnum" 1` for all machine-produced numbers and config values.
- **Do** size primary touch targets to a minimum of 44px height and use full-column-width buttons for the fastener selector.
- **Do** fill the entire display panel with Fault Red on error states — error must interrupt, not annotate.
- **Do** use the 20px corner radius only on consumer-facing confirmation dialogs that require a deliberate operator decision.
- **Do** use near-zero radius (0–0.25rem) or zero radius on all kiosk and operator panel surfaces.
- **Do** communicate focus with a 4px inset Counting Light ring — large enough to read on a bright reflective screen with gloves.
- **Do** keep the camera feed column full-height and full-width as the visual anchor of the layout.
- **Do** use Thai as the primary label language; reserve English for technical strings (GPIO, operator, camera, system, engine names).

### Don't:
- **Don't** make it look like a SaaS dashboard, a mobile app, a decorative cyber interface, or a colorful consumer UI.
- **Don't** use too many buttons, tiny touch targets, unnecessary data panels, ornamental motion, or loud saturated colors.
- **Don't** apply gradient text, glassmorphism, hero metrics, identical card grids, or side-stripe accent borders — all prohibited.
- **Don't** use more than one accent color. There is no secondary accent in this system.
- **Don't** animate layout properties or add entrance choreography. State changes are color-only transitions.
- **Don't** apply Factory Beige to the display center column or Display Void to the shell panels. The zone boundary is absolute.
- **Don't** use IBM Plex Mono for body copy, headings, or navigation labels. Mono is for machine numbers only.
- **Don't** round kiosk panel buttons or operator controls beyond 0.25rem. The near-square edge is part of the industrial character.
- **Don't** use the 20px corner radius on kiosk or operator surfaces. Softness belongs only on dialogs that interrupt normal operation.
- **Don't** add color-only error states that annotate the display panel. Replace the entire panel background with Fault Red.
