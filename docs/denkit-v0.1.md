# Fox Den Midnight (DenKit v0.1)

The user-approved headphone fox is the shared mascot. This milestone uses it on
the Portal entry experience and Jellyfin browser login, while keeping the Music
and Movies/TV operational workspaces deliberately restrained. The original PNG
is stored once with Portal static assets and served to Jellyfin through ingress.

DenKit v0.1 is the shared visual foundation for the Fox Den Media Portal, Music workspace, and Movies/TV workspace. It is intentionally CSS-only: application routes, templates, authentication, identity assertions, APIs, databases, workers, networking, and deployment behavior remain unchanged.

## Canonical tokens

| Token | Value | Purpose |
| --- | --- | --- |
| `--den-midnight` | `#0B1423` | Page and application background |
| `--den-slate` | `#25384B` | Secondary and interactive surfaces |
| `--den-mint` | `#97E7CA` | Links, focus, progress, and healthy states |
| `--den-coral` | `#F68D91` | Primary actions, selection, and brand accent |
| `--den-amber` | `#F5AD66` | Warnings and informational emphasis |
| `--den-cream` | `#F7F5E9` | Primary text on dark surfaces |
| `--den-raised` | `#142335` | Cards, panels, sidebars, and navigation |
| `--den-border` | `#36495D` | Dividers, outlines, and subtle boundaries |
| `--den-muted` | `#AFC0D1` | Secondary text and disabled states |
| `--den-critical` | `#EF5261` | Errors, destructive actions, and critical alerts |

Each application owns a small `denkit.css` layer loaded after its existing component styles. The canonical names above are consistent, while legacy aliases such as `--orange`, `--green`, and `--accent` are mapped locally so the visual refresh does not require component rewrites.

## Semantic rules

- Coral is reserved for primary actions, selected navigation, and Fox Den accents.
- Mint represents healthy states, progress, secondary links, and keyboard focus.
- Amber represents pending work and warnings.
- Critical red represents errors and destructive states; text and labels continue to accompany color.
- Cream and muted blue-gray text are used on Midnight, Raised Surface, and Slate backgrounds.
- Bright controls use Midnight foreground text for contrast.

The theme includes visible `:focus-visible` outlines, reduced-motion overrides, and dark scrollbars. It preserves the existing responsive layouts and uses no external fonts, images, JavaScript, or runtime theme service.

## Application layers

- Portal: `apps/portal/src/foxden_portal/static/denkit.css`
- Music: `apps/music/backend/src/foxden_music/static/denkit.css`
- Movies/TV: `apps/media/app/static/denkit.css`
- Standalone Music compatibility: `apps/music/frontend/static/denkit.css`

The contained browser chrome inherits these workspace tokens. The native Firefox page, qBittorrent UI, and `/server-browser/` application content are intentionally not themed by DenKit v0.1.
