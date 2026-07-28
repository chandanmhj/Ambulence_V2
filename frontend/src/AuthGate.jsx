import React, { useState, useEffect } from "react";
import Login from "./components/Login.jsx";
import Signup from "./components/Signup.jsx";
import ForgotPassword from "./components/ForgotPassword.jsx";
import ResetPassword from "./components/ResetPassword.jsx";
import VerifyEmailPending from "./components/VerifyEmailPending.jsx";
import LandingPage from "./components/LandingPage.jsx";
import App from "./App.jsx";
import { verifyStoredToken, verifyEmail, clearAuth } from "./authApi.js";

function getUrlToken(paramName) {
  const params = new URLSearchParams(window.location.search);
  return params.get(paramName);
}

function clearUrlParams() {
  window.history.replaceState({}, "", window.location.pathname);
}

export default function AuthGate() {
  const [checking, setChecking] = useState(true);
  const [user, setUser] = useState(null);
  const [screen, setScreen] = useState("landing"); // "landing" | "login" | "signup" | "forgot"
  const [emailVerifyStatus, setEmailVerifyStatus] = useState(null); // null | "verifying" | "success" | "error"

  const resetToken = getUrlToken("reset_token");
  const verifyToken = getUrlToken("verify_token");

  useEffect(() => {
    (async () => {
      // A verification link was clicked - confirm it, regardless of current login state.
      if (verifyToken) {
        setEmailVerifyStatus("verifying");
        try {
          await verifyEmail(verifyToken);
          setEmailVerifyStatus("success");
        } catch {
          setEmailVerifyStatus("error");
        }
        clearUrlParams();
      }

      const verified = await verifyStoredToken();
      setUser(verified);
      setChecking(false);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleAuthenticated = (data) => {
    setUser({ email: data.email, name: data.name, is_verified: data.is_verified });
  };

  const handleLogout = () => {
    clearAuth();
    setUser(null);
    setScreen("landing");
  };

  if (checking) {
    return <div className="auth-loading">Loading...</div>;
  }

  // Password reset link was opened - show the reset form regardless of login state.
  if (resetToken) {
    return (
      <ResetPassword
        token={resetToken}
        onDone={() => {
          clearUrlParams();
          window.location.reload();
        }}
      />
    );
  }

  // Just clicked a verification link - show the result before anything else.
  if (emailVerifyStatus === "verifying") {
    return <div className="auth-loading">Verifying your email...</div>;
  }
  if (emailVerifyStatus === "success" || emailVerifyStatus === "error") {
    return (
      <div className="auth-screen">
        <div className="auth-card">
          <h1 className="auth-title">{emailVerifyStatus === "success" ? "Email verified" : "Verification failed"}</h1>
          <p className="auth-subtitle">
            {emailVerifyStatus === "success"
              ? "Your email has been verified. You can now sign in."
              : "This verification link is invalid or has expired."}
          </p>
          <button className="btn-primary auth-submit" onClick={() => setEmailVerifyStatus(null)}>
            Continue
          </button>
        </div>
      </div>
    );
  }

  if (!user) {
    if (screen === "signup") {
      return (
        <Signup
          onAuthenticated={handleAuthenticated}
          onSwitchToLogin={() => setScreen("login")}
          onBackToLanding={() => setScreen("landing")}
        />
      );
    }
    if (screen === "login") {
      return (
        <Login
          onAuthenticated={handleAuthenticated}
          onSwitchToSignup={() => setScreen("signup")}
          onSwitchToForgotPassword={() => setScreen("forgot")}
          onBackToLanding={() => setScreen("landing")}
        />
      );
    }
    if (screen === "forgot") {
      return <ForgotPassword onBackToLogin={() => setScreen("login")} />;
    }
    return <LandingPage onSignIn={() => setScreen("login")} onSignUp={() => setScreen("signup")} />;
  }

  if (user.is_verified === false) {
    return <VerifyEmailPending email={user.email} onLogout={handleLogout} />;
  }

  return <App user={user} onLogout={handleLogout} />;
}
