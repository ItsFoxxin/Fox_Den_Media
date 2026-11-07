# Fox Den Media 0.9.2 — Server browser Home control

## Problem

The optional Firefox container uses `BROWSER_HOME_URL` for its startup page
(`FF_OPEN_URL`). The Music request browser's **Downloader home** button used
`MUSIC_REQUEST_PROVIDER_URL` for name-based requests instead. Those values can
differ: for example, the provider can point to MusicBrainz while Firefox starts
at SpotiDownloader. The toolbar could therefore send the wrong destination
(or a missing destination) even when Firefox itself was functioning.

## Fix

- The integrated Compose Music service now receives `BROWSER_HOME_URL` too.
- The Music browser view uses that value for the Home button. For standalone
  Music, it falls back to the configured `SPOTIDOWNLOADER_URL`.
- Validate custom Home values as public HTTPS URLs without credentials,
  fragments, custom ports, or control characters.
- The existing same-origin noVNC/RFB bridge still reuses the current viewer
  session; it does **not** create a second VNC connection, bypass user prompts,
  or copy provider data into the clipboard.
- The toolbar distinguishes disconnected, read-only, invalid-home, and
  unsupported viewer errors. A visible manual URL fallback remains usable.
- A synthetic same-origin noVNC fixture checks that clicking Home sends
  Escape, Ctrl+L, the configured HTTPS URL, and Enter.

## Acceptance test (separate disposable environment)

1. Deploy a new isolated Compose project from this PR's reviewed commit,
   including Music and the supported pinned Firefox image. Do not update
   Test57, Test51, or production during acceptance.
2. Configure `BROWSER_HOME_URL=https://spotidownloader.com/` and optionally
   configure a **different** `MUSIC_REQUEST_PROVIDER_URL` for metadata.
3. Open a Music request's server browser, navigate to a harmless alternate page,
   then click **Downloader home**. Verify remote Firefox's address bar shows
   the configured Home URL. Verify the browser does not restart and downloads
   are not discarded.
4. Disconnect the viewer or enable view-only mode, click Home, and confirm a
   relevant error instead of a false success. Use the manual URL fallback.
5. Reconnect and repeat on desktop and mobile. Verify no new WebSocket or
   unauthenticated browser port is exposed.
6. Check startup with a custom valid HTTPS homepage and confirm the toolbar
   matches the container's start page.
7. Verify `BROWSER_HOME_URL` and `MUSIC_REQUEST_PROVIDER_URL` affect only
   their intended destinations. Confirm login, session authorization and
   browser-download staging remain independent.

## Limits

The fixture validates JavaScript/Home dispatch against a simulated noVNC
viewer. It does not establish that the pinned actual Firefox image accepts
the keystrokes on every platform. Real NAS/browser acceptance is required.

This patch does not change download watcher logic, the MusicBrainz request
resolution process, or the separate automatic handoff correction in PR #22.
