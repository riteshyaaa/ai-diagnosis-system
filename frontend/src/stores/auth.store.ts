/**
 * MedFusion AI — Authentication State Store (Zustand)
 */

import { create } from "zustand";
import { authService } from "../services/auth.service";
import type { LoginPayload, RegisterPayload, User } from "../types";

interface AuthState {
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (payload: LoginPayload) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => Promise<void>;
  fetchCurrentUser: () => Promise<void>;
  initialize: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  accessToken: localStorage.getItem("access_token"),
  isAuthenticated: !!localStorage.getItem("access_token"),
  isLoading: false,
  error: null,

  login: async (payload: LoginPayload) => {
    set({ isLoading: true, error: null });
    try {
      const response = await authService.login(payload);
      localStorage.setItem("access_token", response.access_token);
      localStorage.setItem("refresh_token", response.refresh_token);

      set({
        user: response.user,
        accessToken: response.access_token,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
    } catch (err: any) {
      const errorMsg =
        err?.response?.data?.detail || "Authentication failed. Please verify credentials.";
      set({ isLoading: false, error: errorMsg });
      throw err;
    }
  },

  register: async (payload: RegisterPayload) => {
    set({ isLoading: true, error: null });
    try {
      await authService.register(payload);
      // Automatically log in after registration
      const loginRes = await authService.login({
        email: payload.email,
        password: payload.password,
      });
      localStorage.setItem("access_token", loginRes.access_token);
      localStorage.setItem("refresh_token", loginRes.refresh_token);

      set({
        user: loginRes.user,
        accessToken: loginRes.access_token,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
    } catch (err: any) {
      const errorMsg =
        err?.response?.data?.detail || "Registration failed. Please try again.";
      set({ isLoading: false, error: errorMsg });
      throw err;
    }
  },

  logout: async () => {
    set({ isLoading: true });
    try {
      await authService.logout();
    } finally {
      set({
        user: null,
        accessToken: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      });
    }
  },

  fetchCurrentUser: async () => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      set({ user: null, isAuthenticated: false });
      return;
    }

    try {
      set({ isLoading: true });
      const user = await authService.getCurrentUser();
      set({ user, isAuthenticated: true, isLoading: false });
    } catch {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      set({ user: null, accessToken: null, isAuthenticated: false, isLoading: false });
    }
  },

  initialize: async () => {
    const token = localStorage.getItem("access_token");
    if (token) {
      try {
        const user = await authService.getCurrentUser();
        set({ user, accessToken: token, isAuthenticated: true, isLoading: false });
      } catch {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        set({ user: null, accessToken: null, isAuthenticated: false, isLoading: false });
      }
    }
  },

  clearError: () => set({ error: null }),
}));
