// Runs inside the same-origin noVNC frame. Reuse the existing RFB session;
// never create another session or place the remote URL on the host clipboard.
const report = (ok, message = '') =>
  document.dispatchEvent(new CustomEvent('foxden:home-result', { detail: { ok, message } }));

try {
  const source = [...document.querySelectorAll('script[type="module"]')]
    .map((script) => script.textContent)
    .join('\n');
  const match = source.match(/import\s+UI\s+from\s+["']([^"']+)["']/);
  if (!match) throw new Error('Viewer UI module not found');
  const moduleUrl = new URL(match[1], document.baseURI);
  if (moduleUrl.origin !== location.origin || !moduleUrl.pathname.endsWith('/app/ui.js')) {
    throw new Error('Unexpected viewer UI module');
  }
  const { default: UI } = await import(moduleUrl.href);

  let busy = false;
  document.addEventListener('foxden:home', async () => {
    if (busy) return;
    if (!UI.connected || !UI.rfb) {
      report(false, 'The Firefox viewer is disconnected. Reconnect and try again.');
      return;
    }
    if (UI.rfb.viewOnly) {
      report(false, 'Remote keyboard input is disabled in the viewer.');
      return;
    }
    let destination;
    try {
      const raw = window.frameElement?.dataset.homeUrl;
      if (!raw) throw new Error('Missing home URL');
      destination = new URL(raw);
      if (destination.protocol !== 'https:' || !destination.hostname ||
          destination.username || destination.password || destination.hash) {
        throw new Error('Invalid home URL');
      }
    } catch (_) {
      report(false, 'The configured downloader homepage is invalid. Check BROWSER_HOME_URL.');
      return;
    }

    busy = true;
    const rfb = UI.rfb;
    try {
      // Escape browser menus, focus the location bar, then type the validated
      // HTTPS address. Explicitly release Control before typing.
      rfb.sendKey(0xff1b, 'Escape');
      rfb.sendKey(0xffe3, 'ControlLeft', true);
      try { rfb.sendKey(0x6c, 'KeyL'); }
      finally { rfb.sendKey(0xffe3, 'ControlLeft', false); }

      await new Promise((resolve) => setTimeout(resolve, 150));
      if (!UI.connected || UI.rfb !== rfb) throw new Error('Viewer disconnected');
      for (const character of destination.href) {
        rfb.sendKey(character.codePointAt(0));
      }
      rfb.sendKey(0xff0d, 'Enter');
      report(true);
    } catch (_) {
      report(false, 'Could not send the address to Firefox. Enter the homepage manually.');
    } finally {
      busy = false;
    }
  });

  document.dispatchEvent(new CustomEvent('foxden:home-ready'));
} catch (_) {
  document.dispatchEvent(new CustomEvent('foxden:home-unavailable', {
    detail: { message: 'This noVNC viewer does not expose supported remote controls. Enter the homepage manually.' },
  }));
}
