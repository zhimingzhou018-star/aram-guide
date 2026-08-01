(() => {
  const config = window.ARAM_ANALYTICS_CONFIG || {};
  const pendingEvents = [];
  let client = null;

  function isEnabled() {
    return Boolean(config.enabled && config.posthogKey);
  }

  function capture(eventName, properties = {}) {
    if (!isEnabled()) return;
    if (client?.capture) {
      client.capture(eventName, properties);
      return;
    }
    pendingEvents.push([eventName, properties]);
  }

  window.ARAM_ANALYTICS = Object.freeze({ capture, isEnabled });

  if (!config.enabled || !config.posthogKey) return;

  const script = document.createElement("script");
  script.async = true;
  script.crossOrigin = "anonymous";
  script.src = `${config.posthogAssetsHost || "https://us-assets.i.posthog.com"}/static/array.js`;
  script.onload = () => {
    if (!window.posthog?.init) return;
    client = window.posthog.init(config.posthogKey, {
      api_host: config.posthogHost || "https://us.i.posthog.com",
      autocapture: false,
      capture_pageview: false,
      capture_pageleave: false,
      person_profiles: "identified_only",
      disable_session_recording: true,
    });
    const activeClient = client || window.posthog;
    pendingEvents.splice(0).forEach(([eventName, properties]) => {
      activeClient.capture(eventName, properties);
    });
  };
  document.head.appendChild(script);
})();
