import { BACKEND_HTTP } from "./config.js";

const TOKEN_KEY = "ambulance_auth_token";
const USER_KEY = "ambulance_auth_user"; // { email, name }

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser() {
  const raw = localStorage.getItem(USER_KEY);
  return raw ? JSON.parse(raw) : null;
}

function storeAuth(data) {
  localStorage.setItem(TOKEN_KEY, data.access_token);
  localStorage.setItem(USER_KEY, JSON.stringify({ email: data.email, name: data.name, is_verified: data.is_verified }));
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

async function handleAuthResponse(res) {
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Something went wrong");
  }
  storeAuth(data);
  return data;
}

export async function signup(email, password, name) {
  const res = await fetch(`${BACKEND_HTTP}/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, name }),
  });
  return handleAuthResponse(res);
}

export async function login(email, password) {
  const res = await fetch(`${BACKEND_HTTP}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return handleAuthResponse(res);
}

export async function loginWithGoogle(idToken) {
  const res = await fetch(`${BACKEND_HTTP}/auth/google`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token: idToken }),
  });
  return handleAuthResponse(res);
}

// Verifies the stored token is still valid (not expired/revoked) by asking
// the backend - called once on app load so a stale token doesn't silently
// let the user think they're logged in when every real request will 401.
export async function verifyStoredToken() {
  const token = getToken();
  if (!token) return null;

  try {
    const res = await fetch(`${BACKEND_HTTP}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (res.status === 403) {
      const data = await res.json();
      if (data.detail === "EMAIL_NOT_VERIFIED") {
        // Token is valid, just unverified - keep it, don't log out.
        return { ...getStoredUser(), is_verified: false };
      }
    }

    if (!res.ok) {
      clearAuth();
      return null;
    }
    return await res.json();
  } catch {
    // Network error (backend unreachable) - don't log the user out just
    // because of a transient connectivity issue, let them keep trying.
    return getStoredUser();
  }
}

export async function verifyEmail(token) {
  const res = await fetch(`${BACKEND_HTTP}/auth/verify-email`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Verification failed");
  return data;
}

export async function resendVerification() {
  const res = await fetch(`${BACKEND_HTTP}/auth/resend-verification`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeader() },
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Could not resend verification email");
  return data;
}

export async function forgotPassword(email) {
  const res = await fetch(`${BACKEND_HTTP}/auth/forgot-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Something went wrong");
  return data;
}

export async function resetPassword(token, newPassword) {
  const res = await fetch(`${BACKEND_HTTP}/auth/reset-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, new_password: newPassword }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Could not reset password");
  return data;
}

// Convenience helper for building the Authorization header on protected requests.
export function authHeader() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
