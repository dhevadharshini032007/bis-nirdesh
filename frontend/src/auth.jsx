import { createContext, useContext, useEffect, useState } from "react";

export const API_BASE_URL = "http://127.0.0.1:8000";
const TOKEN_KEY = "bisNirdeshToken";
const USER_KEY = "bisNirdeshUser";
const AuthContext = createContext(null);

function savedUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || "null");
  } catch {
    return null;
  }
}

async function requestAuth(path, payload, token) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: payload ? "POST" : "GET",
    headers: {
      ...(payload ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(payload ? { body: JSON.stringify(payload) } : {}),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(data.detail)
      ? data.detail.map((item) => item.msg).join(" ")
      : data.detail || data.error;
    throw new Error(detail || "The request could not be completed.");
  }
  return data;
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState(savedUser);
  const [authLoading, setAuthLoading] = useState(Boolean(token));

  function saveSession(data) {
    localStorage.setItem(TOKEN_KEY, data.token);
    localStorage.setItem(USER_KEY, JSON.stringify(data.user));
    setToken(data.token);
    setUser(data.user);
  }

  async function login(email, password) {
    const data = await requestAuth("/auth/login", { email, password });
    saveSession(data);
  }

  async function register(details) {
    const data = await requestAuth("/auth/register", details);
    saveSession(data);
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setToken(null);
    setUser(null);
  }

  useEffect(() => {
    if (!token) {
      setAuthLoading(false);
      return;
    }
    let active = true;
    requestAuth("/auth/me", null, token)
      .then((data) => {
        if (!active) return;
        setUser(data.user);
        localStorage.setItem(USER_KEY, JSON.stringify(data.user));
      })
      .catch(() => {
        if (active) logout();
      })
      .finally(() => {
        if (active) setAuthLoading(false);
      });
    return () => { active = false; };
  }, []);

  return <AuthContext.Provider value={{ token, user, authLoading, login, register, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
