import React, { useState } from "react";
import { resendVerification } from "../authApi.js";

export default function VerifyEmailPending({ email, onLogout }) {
  const [sent, setSent] = useState(false);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleResend = async () => {
    setError(null);
    setLoading(true);
    try {
      await resendVerification();
      setSent(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <h1 className="auth-title">Verify your email</h1>
        <p className="auth-subtitle">
          We sent a verification link to <strong>{email}</strong>. Click it to activate your account.
        </p>

        {sent && <div className="auth-success">Verification email resent.</div>}
        {error && <div className="auth-error">{error}</div>}

        <button className="btn-primary auth-submit" onClick={handleResend} disabled={loading}>
          {loading ? "Sending..." : "Resend verification email"}
        </button>

        <p className="auth-switch">
          <button className="link-btn" onClick={onLogout}>
            Sign out
          </button>
        </p>
      </div>
    </div>
  );
}
