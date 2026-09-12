/**
 * MedFusion AI — Clinical Staff Login Form Component
 */

import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Lock, Mail, AlertCircle, ShieldCheck, Activity } from "lucide-react";
import { useAuthStore } from "../../stores/auth.store";
import { LoadingSpinner } from "../common/LoadingSpinner";

export const LoginForm: React.FC = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const { login, isLoading, error } = useAuthStore();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) return;

    try {
      await login({ email, password });
      navigate("/cases");
    } catch {
      // Error is tracked in store
    }
  };

  const handleFillDemo = (demoEmail: string) => {
    setEmail(demoEmail);
    setPassword("MedFusion#2026Secure!");
  };

  return (
    <div className="w-full max-w-md rounded-2xl border border-gray-200 bg-white p-8 shadow-xl">
      {/* Header */}
      <div className="text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-tr from-primary-700 to-primary-500 text-white shadow-lg shadow-primary-500/25">
          <Activity className="h-6 w-6" />
        </div>
        <h2 className="mt-4 text-2xl font-black tracking-tight text-gray-900">
          MedFusion <span className="text-primary-600">AI</span>
        </h2>
        <p className="mt-1 text-xs text-gray-500">
          Assistive Multimodal Clinical Decision Support System (CDSS)
        </p>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="mt-6 flex items-start gap-2.5 rounded-xl bg-rose-50 border border-rose-200 p-3.5 text-xs text-rose-800">
          <AlertCircle className="h-4 w-4 text-rose-600 flex-shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {/* Form */}
      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-gray-700">
            Institutional Email / ID
          </label>
          <div className="relative mt-1">
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
              <Mail className="h-4 w-4 text-gray-400" />
            </div>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="clinician@hospital.org"
              className="block w-full rounded-xl border border-gray-300 bg-gray-50/50 pl-10 pr-3 py-2.5 text-sm text-gray-900 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-gray-700">
            Clinical Authorization Password
          </label>
          <div className="relative mt-1">
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
              <Lock className="h-4 w-4 text-gray-400" />
            </div>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              className="block w-full rounded-xl border border-gray-300 bg-gray-50/50 pl-10 pr-3 py-2.5 text-sm text-gray-900 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="mt-2 flex w-full items-center justify-center rounded-xl bg-primary-600 py-3 text-sm font-bold text-white shadow-md shadow-primary-600/25 transition-all hover:bg-primary-700 active:scale-[0.99] disabled:opacity-50"
        >
          {isLoading ? (
            <LoadingSpinner size="sm" className="p-0 text-white" />
          ) : (
            "Authenticate Clinical Session"
          )}
        </button>
      </form>

      {/* Demo Credentials Helper */}
      <div className="mt-6 rounded-xl border border-gray-100 bg-gray-50/80 p-3.5 text-xs">
        <div className="flex items-center gap-1.5 font-bold text-gray-700">
          <ShieldCheck className="h-3.5 w-3.5 text-primary-600" />
          <span>Quick Login (Hospital Demo Personas)</span>
        </div>
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          <button
            type="button"
            onClick={() => handleFillDemo("dr.chen@medfusion.local")}
            className="rounded-lg border border-gray-200 bg-white px-2 py-1 text-[11px] font-medium text-gray-700 hover:border-primary-400 hover:text-primary-600"
          >
            Dr. Chen (Clinician)
          </button>
          <button
            type="button"
            onClick={() => handleFillDemo("dr.patel@medfusion.local")}
            className="rounded-lg border border-gray-200 bg-white px-2 py-1 text-[11px] font-medium text-gray-700 hover:border-primary-400 hover:text-primary-600"
          >
            Dr. Patel (Radiologist)
          </button>
          <button
            type="button"
            onClick={() => handleFillDemo("admin@medfusion.local")}
            className="rounded-lg border border-gray-200 bg-white px-2 py-1 text-[11px] font-medium text-gray-700 hover:border-primary-400 hover:text-primary-600"
          >
            Admin / Compliance
          </button>
        </div>
      </div>

      {/* Register Link */}
      <div className="mt-6 text-center text-xs text-gray-500">
        New clinical staff member?{" "}
        <Link to="/register" className="font-bold text-primary-600 hover:underline">
          Register Institutional Profile
        </Link>
      </div>
    </div>
  );
};
