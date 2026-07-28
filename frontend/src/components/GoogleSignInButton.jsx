import React, { useEffect, useRef } from "react";
import { GOOGLE_CLIENT_ID } from "../config.js";

// Loads Google's Identity Services script once and renders their official
// Sign-In button into a div we control. On success, Google calls back with
// a signed ID token - we hand that to onSuccess, which sends it to our own
// backend for verification (see auth.py / auth_routes.py).
export default function GoogleSignInButton({ onSuccess, onError }) {
  const buttonRef = useRef(null);
  const scriptLoadedRef = useRef(false);

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return; // not configured - button simply won't render

    function initialize() {
      if (!window.google || scriptLoadedRef.current) return;
      scriptLoadedRef.current = true;

      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: (response) => {
          if (response.credential) {
            onSuccess(response.credential);
          } else {
            onError && onError("Google sign-in did not return a credential");
          }
        },
      });

      window.google.accounts.id.renderButton(buttonRef.current, {
        theme: "filled_black",
        size: "large",
        width: 300,
        text: "continue_with",
      });
    }

    if (window.google) {
      initialize();
      return;
    }

    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.onload = initialize;
    document.body.appendChild(script);

    // Deliberately not removing the script on unmount - Google's client is
    // meant to be loaded once per page and reused.
  }, [onSuccess, onError]);

  if (!GOOGLE_CLIENT_ID) {
    return (
      <div className="google-btn-placeholder">
        Google sign-in not configured (set VITE_GOOGLE_CLIENT_ID)
      </div>
    );
  }

  return <div ref={buttonRef} className="google-btn-container" />;
}
