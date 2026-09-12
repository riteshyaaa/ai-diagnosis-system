/**
 * MedFusion AI — Authentication API Service
 */

import api from "./api";
import type {
  AuthTokens,
  LoginPayload,
  RegisterPayload,
  User,
} from "../types";

export const authService = {
  /**
   * Authenticate with email & password to retrieve JWT tokens.
   */
  async login(payload: LoginPayload): Promise<AuthTokens> {
    const { data } = await api.post<AuthTokens>("/auth/login", payload);
    return data;
  },

  /**
   * Register a new user account.
   */
  async register(payload: RegisterPayload): Promise<User> {
    const { data } = await api.post<User>("/auth/register", payload);
    return data;
  },

  /**
   * Fetch currently authenticated user profile.
   */
  async getCurrentUser(): Promise<User> {
    const { data } = await api.get<User>("/auth/me");
    return data;
  },

  /**
   * Invalidate current session and tokens.
   */
  async logout(): Promise<void> {
    try {
      await api.post("/auth/logout");
    } catch {
      // Best-effort logout
    } finally {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
    }
  },
};
