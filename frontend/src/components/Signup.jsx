import React, { useState } from "react";
import { signup, loginWithGoogle } from "../authApi.js";
import GoogleSignInButton from "./GoogleSignInButton.jsx";

export default function Signup({ onAuthenticated, onSwitchToLogin, onBackToLanding }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }

    setLoading(true);
    try {
      const data = await signup(email, password, name || null);
      onAuthenticated(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSuccess = async (idToken) => {
    setError(null);
    try {
      const data = await loginWithGoogle(idToken);
      onAuthenticated(data);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="auth-screen">
      <div className="auth-card">
        {onBackToLanding && (
          <button className="link-btn auth-back" onClick={onBackToLanding}>
            &larr; Back to home
          </button>
        )}
        <h1 className="auth-title">Create account</h1>
        <p className="auth-subtitle">Bangalore Emergency Vehicle Routing System</p>

        <form onSubmit={handleSubmit}>
          <div className="field">
            <label>Name (optional)</label>
            <input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
          </div>
          <div className="field">
            <label>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </div>
          <div className="field">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="new-password"
            />
            <div className="field-hint">At least 8 characters</div>
          </div>

          {error && <div className="auth-error">{error}</div>}

          <button type="submit" className="btn-primary auth-submit" disabled={loading}>
            {loading ? "Creating account..." : "Create account"}
          </button>
        </form>

        <div className="auth-divider">or</div>

        <GoogleSignInButton onSuccess={handleGoogleSuccess} onError={setError} />

        <p className="auth-switch">
          Already have an account?{" "}
          <button className="link-btn" onClick={onSwitchToLogin}>
            Sign in
          </button>
        </p>
      </div>
    </div>
  );
}
