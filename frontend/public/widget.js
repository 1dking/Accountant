/**
 * O-Brain embeddable lead-capture widget loader (Arivio widget.js port).
 *
 * Usage on a third-party site:
 *   <script src="https://your-domain/widget.js" data-widget-key="KEY" async></script>
 *
 * Deliberately does almost nothing: it injects a single iframe pointing
 * at /embed/{key} on THIS origin and resizes it on postMessage from the
 * iframe's own JS. All config fetching, theming, and form submission
 * happen inside that iframe (same-origin to the API), so this loader
 * never needs to fetch anything cross-origin itself.
 */
(function () {
  var script = document.currentScript;
  if (!script) return;
  var widgetKey = script.getAttribute('data-widget-key');
  if (!widgetKey) return;

  var origin = new URL(script.src).origin;
  var COLLAPSED = { width: '64px', height: '64px' };

  var iframe = document.createElement('iframe');
  iframe.src = origin + '/embed/' + encodeURIComponent(widgetKey);
  iframe.title = 'Contact us';
  iframe.setAttribute('scrolling', 'no');
  iframe.style.position = 'fixed';
  iframe.style.bottom = '20px';
  iframe.style.border = '0';
  iframe.style.zIndex = '2147483000';
  iframe.style.colorScheme = 'light';
  iframe.style.borderRadius = '16px';
  iframe.style.boxShadow = '0 8px 30px rgba(0,0,0,0.12)';
  iframe.style.transition = 'width 0.2s ease, height 0.2s ease';
  iframe.style.width = COLLAPSED.width;
  iframe.style.height = COLLAPSED.height;
  iframe.style.boxShadow = 'none';
  // Position (left/right) is applied once the iframe tells us via
  // postMessage — defaults to right until then.
  iframe.style.right = '20px';

  function onMessage(event) {
    if (event.origin !== origin) return;
    var data = event.data;
    if (!data || data.source !== 'obrain-widget') return;

    if (data.type === 'resize') {
      iframe.style.width = data.width;
      iframe.style.height = data.height;
      iframe.style.boxShadow = data.expanded ? '0 8px 30px rgba(0,0,0,0.12)' : 'none';
    } else if (data.type === 'position' && data.position === 'bottom-left') {
      iframe.style.right = 'auto';
      iframe.style.left = '20px';
    }
  }

  window.addEventListener('message', onMessage);

  function mount() {
    document.body.appendChild(iframe);
  }
  if (document.body) {
    mount();
  } else {
    document.addEventListener('DOMContentLoaded', mount);
  }
})();
