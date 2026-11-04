# Fox Den Media branding specification

**Status:** Approved direction; implementation deferred<br>
**Specification version:** 0.1<br>
**Prepared:** 2026-11-04<br>
**Implementation gate:** Do not implement these placements until the 0.9.0
migration rehearsal is complete and its migration-critical findings are
resolved or explicitly accepted.

This document defines the shared visual direction for the next Fox Den Media
branding pass. It is deliberately documentation-only. It does not change
application templates, styles, routes, images, containers, deployment files,
or migration behavior.

## Source hierarchy

When references disagree, use this order:

1. The repository asset
   `apps/portal/src/foxden_portal/static/fox-den-mascot.png` is the canonical
   mascot and the source of truth for production UI.
2. The supplied character turnaround/expression sheet is a consistency
   reference for any future pose or expression.
3. The existing Fox Den website screenshots define atmosphere, composition,
   and visual rhythm. They are not production artwork and must not be embedded
   in the applications.
4. `docs/denkit-v0.1.md` defines the current shared application tokens and
   semantic color roles.

The supplied original `3405.png` is byte-for-byte identical to the canonical
repository asset:

- Dimensions: `1312 x 1199`
- SHA-256: `6f152440aec3229c4bce831a064ec5f582a8a67e03808743699df3b2e1598de6`

Do not add a second copy under a different application path. Serve or package a
derived build export from this canonical file when a client cannot consume the
Portal asset directly.

## Character invariants

The mascot is a tiny chibi fox, not a realistic or human-proportioned
anthropomorphic character. Every approved appearance must preserve:

- a large rounded head and compact seated body;
- oversized upright ears with dark tips and cream inner fur;
- large amber-brown eyes, a small dark nose, and a soft rounded muzzle;
- orange fur with cream cheeks, muzzle, chest, ear interiors, and tail tip;
- short paws and a large fluffy curled tail;
- a navy hooded jacket with coral details and a small glowing fox emblem;
- oversized navy headphones with warm coral/orange glowing fox logos;
- a friendly, curious, cozy personality rather than an aggressive or mature
  presentation.

Do not lengthen the limbs or torso, shrink the head or ears, remove the tail,
change the eye color, replace the hoodie/headphones, or reinterpret the mascot
as a human-shaped fox. Avoid photorealistic fur treatment, mascot costumes, and
generic clip-art substitutions.

## Pose and expression governance

The supplied `3388.png` reference sheet (`1280 x 853`, SHA-256
`89ea32f6125f80d01feebdd53a049e45b30640598b1c7b150debeadb76af02b2`)
shows the allowed character language: front, three-quarter, profile, rear,
happy, content, curious, and thoughtful/concerned views.

- Reuse the canonical PNG wherever the seated neutral pose works.
- Treat crops as layout operations, not new character art. Preserve both ears,
  the face, and headphone logos unless a deliberate icon crop is reviewed.
- New expressions or poses require a review artifact beside the canonical
  mascot and turnaround sheet before entering production.
- Do not use generative replacement artwork without explicit review.
- Keep future source/reference files separate from optimized runtime exports.
  Record creator/provenance, dimensions, checksum, intended use, and approval
  status in an asset manifest before committing them.

## Fox Den Midnight atmosphere

The website references establish the desired feeling: a cozy Korean nighttime
cafe layered with a restrained modern operations center.

Use these visual cues:

- deep midnight and slate surfaces with warm, localized light;
- a Seoul-at-night skyline or abstract city-light rhythm as occasional hero
  atmosphere, never as a busy dashboard background;
- sparse cherry blossoms or drifting petals at page edges and transition
  spaces;
- warm lantern/cafe highlights, wood-toned warmth, and soft window glow;
- generous rounded panels, thin borders, and clear depth between the page,
  raised cards, and controls;
- cream typography, coral primary actions, mint focus/healthy states, and amber
  warnings or warm highlights;
- Korean-inspired details used respectfully and sparingly, with Korean copy
  only when it is meaningful and reviewed rather than decorative gibberish.

Technical and dense operational screens should remain restrained. Put scenery
in entry, empty, onboarding, and media-discovery surfaces; do not reduce log,
queue, status, table, or form readability.

## Canonical design tokens

| Role | Value | Usage |
| --- | --- | --- |
| Midnight | `#0B1423` | Primary page background |
| Raised | `#142335` | Cards, navigation, and panels |
| Slate | `#25384B` | Secondary surfaces and controls |
| Border | `#36495D` | Dividers and quiet outlines |
| Mint | `#97E7CA` | Focus, links, healthy and progress states |
| Coral | `#F68D91` | Primary actions, active navigation, brand accents |
| Amber | `#F5AD66` | Pending states, warnings, and warm emphasis |
| Cream | `#F7F5E9` | Primary text on dark surfaces |
| Muted | `#AFC0D1` | Supporting and disabled text |
| Critical | `#EF5261` | Errors and destructive actions |

Use the typography already established in the current Midnight/DenKit work.
Do not add a competing font system. Preserve visible keyboard focus, text labels
alongside color, reduced-motion behavior, readable contrast, and responsive
layouts.

## Proposed placements

These are proposals for the post-rehearsal branding pass, not implemented
requirements in 0.9.0.

| Surface | Proposed mascot treatment | Atmosphere and UI direction | Priority |
| --- | --- | --- | --- |
| Portal sign-in and first-run setup | Canonical seated PNG as the primary welcome illustration | Quiet midnight-to-slate gradient, restrained petals, warm panel light | High |
| Portal dashboard hero | Continue current canonical mascot use; tune scale and spacing rather than replacing it | Compact city/cafe glow, clear module health and navigation | High |
| Watch & Listen landing | Canonical mascot beside discovery heading or empty state, not over media artwork | Cinematic midnight surface, coral/mint discovery accents, artwork-first rows | High |
| Music request/import landing | Small canonical mascot in welcome or empty state only | Operations workspace stays restrained; coral request action and mint progress | Medium |
| Movies/TV request landing | Small canonical mascot in welcome or empty state only | Match Music structure while keeping movie artwork dominant | Medium |
| Module unavailable/empty states | Canonical mascot with contextual copy; a future reviewed concerned pose may be considered | Clear recovery action, no decorative ambiguity about system state | High |
| Global navigation | Use a purpose-made reviewed icon export derived from the canonical identity, not a tiny full-body raster | Midnight navigation, cream label, coral active state | Medium |
| Jellyfin Web fallback theme | Keep customization isolated; use mascot only on login/empty-state surfaces | Preserve client usability and upgrade safety; never cover playback controls | Medium |
| Mobile web | Use cropped canonical mascot only when it remains legible and does not consume the primary viewport | Single-column layouts, safe areas, large controls, minimal petals/animation | High |
| Admin status, logs, queues, and tables | No large mascot; at most a small brand mark in chrome | Favor density, contrast, state semantics, and scanability | High |
| Error and destructive confirmations | Do not use a cheerful mascot as the only signal | Explicit critical styling, plain-language consequence, safe default action | High |

## Placement rules

- The mascot supports orientation and warmth; it must not obscure status,
  media artwork, playback controls, form fields, or primary actions.
- Use one prominent mascot per viewport at most.
- Avoid repeating the full-body PNG in every card or module tile.
- Never use the mascot as proof that an operation succeeded. Pair states with
  text and existing semantic icons.
- Decorative imagery must use empty alt text. Informative mascot appearances
  need concise context-specific alt text.
- Responsive crops must not create accidental headless, earless, or logo-only
  fragments.
- Respect `prefers-reduced-motion`; petal or glow motion must be optional,
  subtle, and absent from operational tables and forms.

## Asset packaging proposal

After the implementation gate is approved, introduce a small governed asset
package rather than copying files into each application:

```text
packages/denkit/
  tokens/
  assets/
    fox-den-mascot.png        # canonical or generated from canonical source
    manifest.json             # checksum, dimensions, provenance, approval
  css/
  README.md
```

The exact package layout should follow the monorepo packaging decision in force
at implementation time. Until then, the Portal path remains canonical.

Runtime exports may include responsive PNG/WebP sizes and a reviewed square
icon crop. They must be generated reproducibly, keep transparency where
required, and be visually compared with the canonical PNG. Do not overwrite
the original with an optimized derivative.

## Review checklist for future implementation

- [ ] The 0.9.0 migration rehearsal is complete and the branding pass has
  separate approval.
- [ ] Changes are isolated from migration, backup, restore, VPN, database, and
  deployment-critical fixes.
- [ ] The canonical mascot checksum remains known and the original is retained.
- [ ] Any new pose/expression has explicit visual approval against the
  turnaround sheet.
- [ ] Portal, Music, Movies/TV, Watch & Listen, and Jellyfin fallback surfaces
  use the same tokens and state semantics.
- [ ] Desktop and mobile screenshots are reviewed at representative widths.
- [ ] Keyboard navigation, focus, contrast, reduced motion, alt text, and zoom
  behavior pass accessibility review.
- [ ] Dense operational views remain readable and are not over-decorated.
- [ ] No credentials, production media, private hostnames, or NAS details appear
  in screenshots or bundled assets.
- [ ] Application, container, and migration regression suites remain green.

## Current boundary

This specification does not authorize or include UI implementation, new mascot
artwork, new runtime assets, website-image reuse, production deployment, or
changes to the 0.9.0 migration rehearsal. Those remain separate review gates.
