/**
 * MedFusion AI — Staff Registration Form Component
 */

import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Lock, Mail, User, AlertCircle, Activity } from "lucide-react";
import { useAuthStore } from "../../stores/auth.store";
import { UserRole } from "../../types";
import { LoadingSpinner } from "../common/LoadingSpinner";

export const RegisterForm: React.FC = () => {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [role, setRole] = useState<UserRole>(UserRole.CLINICIAN);
  const [department, setDepartment] = useState("Cardiology & Pulmonology");
  const [validationError, setValidationError] = useState<string | null>(null);

  const { register, isLoading, error } = useAuthStore();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    if (password !== confirmPassword) {
      setValidationError("Passwords do not match.");
      return;
    }

    if (password.length < 8) {
      setValidationError("Password must be at least 8 characters with high clinical entropy.");
      return;
    }

    try {
      await register({
        full_name: fullName,
        email,
        password,
        role,
        department,
      });
      navigate("/cases");
    } catch {
      // Error handled in store
    }
  };

  return (
    <div className="w-full max-w-md rounded-2xl border border-gray-200 bg-white p-8 shadow-xl">
      <div className="text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-tr from-primary-700 to-primary-500 text-white shadow-lg shadow-primary-500/25">
          <Activity className="h-6 w-6" />
        </div>
        <h2 className="mt-4 text-2xl font-black tracking-tight text-gray-900">
          Staff Registration
        </h2>
        <p className="mt-1 text-xs text-gray-500">
          Enroll your licensed credentials into the MedFusion CDSS network
        </p>
      </div>

      {(error || validationError) && (
        <div className="mt-6 flex items-start gap-2.5 rounded-xl bg-rose-50 border border-rose-200 p-3.5 text-xs text-rose-800">
          <AlertCircle className="h-4 w-4 text-rose-600 flex-shrink-0 mt-0.5" />
          <span>{validationError || error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="mt-6 space-y-3.5">
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-gray-700">
            Full Medical Name & Title
          </label>
          <div className="relative mt-1">
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
              <User className="h-4 w-4 text-gray-400" />
            </div>
            <input
              type="text"
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Dr. Elena Vance, MD"
              className="block w-full rounded-xl border border-gray-300 bg-gray-50/50 pl-10 pr-3 py-2 text-sm text-gray-900 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-gray-700">
            Institutional Email
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
              placeholder="e.vance@hospital.org"
              className="block w-full rounded-xl border border-gray-300 bg-gray-50/50 pl-10 pr-3 py-2 text-sm text-gray-900 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-gray-700">
              Clinical Role
            </label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as UserRole)}
              className="mt-1 block w-full rounded-xl border border-gray-300 bg-gray-50/50 px-3 py-2 text-sm text-gray-900 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20"
            >
              <option value={UserRole.CLINICIAN}>Clinician</option>
              <option value={UserRole.RADIOLOGIST}>Radiologist</option>
              <option value={UserRole.AUDITOR}>Auditor</option>
              <option value={UserRole.ADMIN}>Administrator</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-gray-700">
              Department
            </label>
            <div className="relative mt-1">
              <input
                type="text"
                required
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                placeholder="Pulmonology"
                className="block w-full rounded-xl border border-gray-300 bg-gray-50/50 px-3 py-2 text-sm text-gray-900 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20"
              />
            </div>
          </div>
        </div>

        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-gray-700">
            Authorization Password
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
              className="block w-full rounded-xl border border-gray-300 bg-gray-50/50 pl-10 pr-3 py-2 text-sm text-gray-900 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-gray-700">
            Confirm Password
          </label>
          <div className="relative mt-1">
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
              <Lock className="h-4 w-4 text-gray-400" />
            </div>
            <input
              type="password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="••••••••••••"
              className="block w-full rounded-xl border border-gray-300 bg-gray-50/50 pl-10 pr-3 py-2 text-sm text-gray-900 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="mt-4 flex w-full items-center justify-center rounded-xl bg-primary-600 py-3 text-sm font-bold text-white shadow-md shadow-primary-600/25 transition-all hover:bg-primary-700 active:scale-[0.99] disabled:opacity-50"
        >
          {isLoading ? (
            <LoadingSpinner size="sm" className="p-0 text-white" />
          ) : (
            "Complete Staff Enrollment"
          )}
        </button>
      </form>

      <div className="mt-6 text-center text-xs text-gray-500">
        Already registered?{" "}
        <Link to="/login" className="font-bold text-primary-600 hover:underline">
          Sign in to Clinical Session
        </Link>
      </div>
    </div>
  );
};
