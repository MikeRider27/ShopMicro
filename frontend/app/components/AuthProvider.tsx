"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";

interface AuthContextValue {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let savedToken: string | null = null;
    let savedUser: User | null = null;
    try {
      savedToken = localStorage.getItem("token");
      const rawUser = localStorage.getItem("user");
      savedUser = rawUser ? JSON.parse(rawUser) : null;
    } catch {
      // localStorage no disponible
    }

    if (!savedToken || !savedUser) {
      setLoading(false);
      return;
    }

    // No confiamos ciegamente en lo guardado: si el token ya expiró (la
    // pestaña quedó abierta más de JWT_ACCESS_TOKEN_EXPIRES_MINUTES), lo
    // detectamos acá en vez de que el usuario vea el navbar como
    // "logueado" y recién se entere al intentar comprar algo. api.me()
    // dispara el mismo flujo de "sesión expirada" que cualquier otra
    // llamada autenticada (ver lib/api.ts) si el token ya no es válido.
    setToken(savedToken);
    setUser(savedUser);
    api
      .me(savedToken)
      .catch(() => {
        // El 401 ya disparó la limpieza + redirect en lib/api.ts.
      })
      .finally(() => setLoading(false));
  }, []);

  const persist = (newToken: string, newUser: User) => {
    setToken(newToken);
    setUser(newUser);
    try {
      localStorage.setItem("token", newToken);
      localStorage.setItem("user", JSON.stringify(newUser));
    } catch {
      // ignore
    }
  };

  const login = async (email: string, password: string) => {
    const { access_token, user: loggedUser } = await api.login({ email, password });
    persist(access_token, loggedUser);
  };

  const register = async (email: string, password: string, name: string) => {
    const { access_token, user: newUser } = await api.register({ email, password, name });
    persist(access_token, newUser);
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    try {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
    } catch {
      // ignore
    }
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return ctx;
}
