(() => {
  const frame = document.querySelector('.browser-frame');
  const home = document.querySelector('[data-browser-home]');
  const feedback = document.querySelector('[data-browser-feedback]');
  if (!home || !frame || !feedback) return;

  const notice = (message) => { feedback.textContent = message; };
  let attachedDocument = null;
  home.disabled = true;

  const attach = () => {
    home.disabled = true;
    try {
      const doc = frame.contentDocument;
      if (!doc || doc.URL === 'about:blank') return;
      if (doc === attachedDocument) return;
      attachedDocument = doc;

      doc.addEventListener('foxden:home-ready', () => {
        home.disabled = false;
        notice('');
      });
      doc.addEventListener('foxden:home-unavailable', (event) => {
        home.disabled = true;
        notice(event.detail?.message || 'Remote navigation is unavailable. Enter the configured home address in Firefox manually.');
      });
      doc.addEventListener('foxden:home-result', (event) => {
        home.disabled = false;
        if (event.detail?.ok) {
          notice('Home address sent to Firefox.');
        } else {
          notice(event.detail?.message || 'The browser is not connected. Reconnect the viewer and try again.');
        }
      });

      // Do not inject the bridge twice into one viewer document.
      if (doc.querySelector('[data-foxden-home-bridge]')) return;
      const script = doc.createElement('script');
      script.type = 'module';
      script.src = home.dataset.bridgeUrl;
      script.dataset.foxdenHomeBridge = '';
      script.addEventListener('error', () => {
        home.disabled = true;
        notice('Remote controls could not load. Reload the viewer or enter the home URL manually.');
      });
      doc.head.appendChild(script);
    } catch (_) {
      notice('Remote controls require the same-origin Fox Den viewer. Enter the home URL in Firefox manually.');
    }
  };

  frame.addEventListener('load', attach);
  if (frame.contentDocument?.readyState === 'complete' && frame.contentDocument.URL !== 'about:blank') attach();

  home.addEventListener('click', () => {
    if (home.disabled) return;
    home.disabled = true;
    notice('Sending the home address to Firefox…');
    try {
      const doc = frame.contentDocument;
      if (!doc || doc !== attachedDocument) throw new Error('Viewer changed');
      doc.dispatchEvent(new frame.contentWindow.CustomEvent('foxden:home'));
    } catch (_) {
      home.disabled = false;
      notice('The remote browser disconnected. Reconnect or enter the home URL in Firefox manually.');
    }
  });
})();
