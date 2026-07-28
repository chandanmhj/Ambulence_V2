import React, { useState } from "react";
import { login, loginWithGoogle } from "../authApi.js";
import GoogleSignInButton from "./GoogleSignInButton.jsx";

export default function Login({ onAuthenticated, onSwitchToSignup, onSwitchToForgotPassword, onBackToLanding }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const data = await login(email, password);
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
        <h1 className="auth-title">Sign in</h1>
        <p className="auth-subtitle">Bangalore Emergency Vehicle Routing System</p>

        <form onSubmit={handleSubmit}>
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
              autoComplete="current-password"
            />
            <div className="field-hint">
              <button type="button" className="link-btn" onClick={onSwitchToForgotPassword}>
                Forgot password?
              </button>
            </div>
          </div>

          {error && <div className="auth-error">{error}</div>}

          <button type="submit" className="btn-primary auth-submit" disabled={loading}>
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <div className="auth-divider">or</div>

        <GoogleSignInButton onSuccess={handleGoogleSuccess} onError={setError} />

        <p className="auth-switch">
          Don't have an account?{" "}
          <button className="link-btn" onClick={onSwitchToSignup}>
            Sign up
          </button>
        </p>
      </div>
    </div>
  );
}
