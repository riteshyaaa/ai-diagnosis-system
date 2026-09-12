/**
 * MedFusion AI — Cases Worklist Page
 */

import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Files,
  FilePlus,
  Search,
  Filter,
  ArrowRight,
  Clock,
} from "lucide-react";
import { caseService } from "../services/cases.service";
import { DiagnosticCase, CaseStatus } from "../types";
import { CaseStatusBadge } from "../components/common/Badge";
import { LoadingSpinner } from "../components/common/LoadingSpinner";

export const CasesPage: React.FC = () => {
  const [cases, setCases] = useState<DiagnosticCase[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  useEffect(() => {
    const fetchCases = async () => {
      setIsLoading(true);
      try {
        const response = await caseService.listCases({ limit: 50 });
        setCases(response.items || []);
      } catch (err) {
        console.error("Failed to load clinical cases:", err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchCases();
  }, []);

  const filteredCases = cases.filter((c) => {
    const matchesSearch =
      (c.case_number && c.case_number.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (c.chief_complaint && c.chief_complaint.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (c.patient_id && c.patient_id.toLowerCase().includes(searchQuery.toLowerCase())) ||
      c.id.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === "ALL" || c.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-gray-900 flex items-center gap-2">
            <Files className="h-6 w-6 text-primary-600" />
            Clinical Diagnostic Worklist
          </h1>
          <p className="text-xs text-gray-500">
            Active patient diagnostic cases with multimodal vision &amp; telemetry inference
          </p>
        </div>

        <Link
          to="/cases/new"
          className="inline-flex items-center gap-2 rounded-xl bg-primary-600 px-4 py-2.5 text-xs font-bold text-white shadow-md shadow-primary-600/20 hover:bg-primary-700 active:scale-95 transition-all"
        >
          <FilePlus className="h-4 w-4" />
          Create New Diagnostic Case
        </Link>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
        <div className="relative w-full sm:w-80">
          <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
            <Search className="h-4 w-4 text-gray-400" />
          </div>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by case title, patient hash..."
            className="block w-full rounded-xl border border-gray-200 bg-gray-50/50 pl-9 pr-3 py-2 text-xs text-gray-800 focus:border-primary-500 focus:bg-white focus:outline-none"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <Filter className="h-4 w-4 text-gray-400" />
          <span className="text-xs font-semibold text-gray-600">Status:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-xl border border-gray-200 bg-gray-50/50 px-3 py-2 text-xs font-semibold text-gray-800 focus:border-primary-500 focus:bg-white focus:outline-none"
          >
            <option value="ALL">All Statuses</option>
            <option value={CaseStatus.DRAFT}>Draft</option>
            <option value={CaseStatus.SUBMITTED}>Submitted</option>
            <option value={CaseStatus.PROCESSING}>Processing</option>
            <option value={CaseStatus.COMPLETED}>Completed</option>
            <option value={CaseStatus.REVIEWED}>Reviewed (MD)</option>
          </select>
        </div>
      </div>

      {/* Case List Table / Cards */}
      {isLoading ? (
        <div className="flex h-64 items-center justify-center">
          <LoadingSpinner size="lg" message="Loading clinical diagnostic queue..." />
        </div>
      ) : filteredCases.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-gray-200 bg-white p-12 text-center">
          <Files className="h-12 w-12 text-gray-300" />
          <h3 className="mt-3 text-sm font-bold text-gray-700">No Diagnostic Cases Found</h3>
          <p className="mt-1 text-xs text-gray-400">
            Create your first multimodal diagnostic case to begin CDSS evaluation.
          </p>
          <Link
            to="/cases/new"
            className="mt-4 inline-flex items-center gap-1.5 rounded-xl bg-primary-600 px-4 py-2 text-xs font-bold text-white hover:bg-primary-700"
          >
            <FilePlus className="h-3.5 w-3.5" />
            Create Diagnostic Case
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredCases.map((c) => (
            <Link
              key={c.id}
              to={`/cases/${c.id}`}
              className="group flex flex-col justify-between rounded-2xl border border-gray-200 bg-white p-5 shadow-sm transition-all hover:border-primary-300 hover:shadow-md"
            >
              <div>
                <div className="flex items-start justify-between gap-2">
                  <CaseStatusBadge status={c.status} />
                  <span className="text-[10px] font-mono text-gray-400">
                    {c.case_number || c.id.slice(0, 8)}
                  </span>
                </div>

                <h3 className="mt-3 text-base font-bold text-gray-900 group-hover:text-primary-600 transition-colors line-clamp-1">
                  {c.chief_complaint || `Case ${c.case_number || c.id.slice(0, 8)}`}
                </h3>
                <p className="mt-1 text-xs text-gray-500 line-clamp-2">
                  {c.clinical_notes || "Multimodal thoracic & cardiovascular diagnostic assessment."}
                </p>
              </div>

              <div className="mt-5 border-t border-gray-100 pt-3">
                <div className="flex items-center justify-between text-xs text-gray-500">
                  <div className="flex items-center gap-1">
                    <Clock className="h-3.5 w-3.5 text-gray-400" />
                    <span>{new Date(c.created_at).toLocaleDateString()}</span>
                  </div>

                  <span className="flex items-center gap-1 font-bold text-primary-600 group-hover:translate-x-0.5 transition-transform">
                    Open Case <ArrowRight className="h-3.5 w-3.5" />
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
};
