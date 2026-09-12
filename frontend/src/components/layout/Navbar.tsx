/**
 * MedFusion AI — Primary Navigation Header
 */

import React from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  Activity,
  FilePlus,
  Files,
  BarChart3,
  ShieldAlert,
  LogOut,
  User as UserIcon,
} from "lucide-react";
import clsx from "clsx";
import { useAuthStore } from "../../stores/auth.store";
import { UserRoleBadge } from "../common/Badge";
import { UserRole } from "../../types";

export const Navbar: React.FC = () => {
  const { user, logout } = useAuthStore();
  const location = useLocation();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const navLinks = [
    { name: "Cases Worklist", path: "/cases", icon: Files },
    { name: "New Diagnostic Case", path: "/cases/new", icon: FilePlus },
    { name: "Concordance Analytics", path: "/analytics", icon: BarChart3 },
  ];

  if (user?.role === UserRole.ADMIN || user?.role === UserRole.AUDITOR) {
    navLinks.push({ name: "Audit Trail", path: "/audit", icon: ShieldAlert });
  }

  return (
    <header className="sticky top-0 z-40 border-b border-gray-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Brand Logo */}
        <div className="flex items-center gap-8">
          <Link to="/cases" className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-primary-700 to-primary-500 text-white shadow-md shadow-primary-500/20">
              <Activity className="h-5 w-5" />
            </div>
            <div>
              <span className="text-base font-black tracking-tight text-gray-900">
                MedFusion<span className="text-primary-600">AI</span>
              </span>
              <span className="ml-1.5 rounded bg-primary-50 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-primary-700 border border-primary-100">
                CDSS v2.0
              </span>
            </div>
          </Link>

          {/* Nav Items */}
          <nav className="hidden md:flex items-center gap-1">
            {navLinks.map((link) => {
              const Icon = link.icon;
              const isActive = location.pathname === link.path || (link.path !== "/cases" && location.pathname.startsWith(link.path));
              return (
                <Link
                  key={link.path}
                  to={link.path}
                  className={clsx(
                    "flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-semibold transition-colors",
                    isActive
                      ? "bg-primary-50 text-primary-700"
                      : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                  )}
                >
                  <Icon className={clsx("h-4 w-4", isActive ? "text-primary-600" : "text-gray-400")} />
                  {link.name}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* User Info & Actions */}
        <div className="flex items-center gap-4">
          {user && (
            <div className="hidden sm:flex items-center gap-2.5 pr-2 border-r border-gray-200">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gray-100 text-gray-600">
                <UserIcon className="h-4 w-4" />
              </div>
              <div className="flex flex-col text-right">
                <span className="text-xs font-bold text-gray-800">{user.full_name}</span>
                <span className="text-[10px] text-gray-500">{user.email}</span>
              </div>
              <UserRoleBadge role={user.role} />
            </div>
          )}

          <button
            type="button"
            onClick={handleLogout}
            className="flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 hover:text-rose-600 transition-colors"
            title="Log Out of CDSS Session"
          >
            <LogOut className="h-4 w-4 text-gray-500 group-hover:text-rose-600" />
            <span>Sign Out</span>
          </button>
        </div>
      </div>
    </header>
  );
};
