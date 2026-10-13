import React, { useEffect, useState } from "react";
import { AlertCircle, ChevronLeft, ChevronRight, ListChecks, ShieldAlert } from "lucide-react";

import { auditService } from "../services/audit.service";
import type { AuditEvent } from "../types";
import { apiErrorMessage } from "../utils/apiError";

const PAGE_SIZE = 25;
const RESOURCE_TYPES = ["patient", "case", "image", "clinical_record", "prediction", "explanation", "review", "user", "system"];

function formatLabel(value: string): string {
  return value.replace(/_/g, " ");
}

function formatTimestamp(value: string): string {
  const timestamp = new Date(value);
  return Number.isNaN(timestamp.getTime()) ? "Unknown time" : timestamp.toLocaleString();
}

export const AuditPage: React.FC = () => {
  const [items, setItems] = useState<AuditEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [resourceType, setResourceType] = useState("all");
  const [page, setPage] = useState(0);
  const [reloadKey, setReloadKey] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);

    auditService.listEvents({
      resource_type: resourceType === "all" ? undefined : resourceType,
      skip: page * PAGE_SIZE,
      limit: PAGE_SIZE,
    }).then((response) => {
      if (cancelled) return;
      setItems(response.items);
      setTotal(response.total);
    }).catch((requestError: unknown) => {
      if (!cancelled) {
        setItems([]);
        setTotal(0);
        setError(apiErrorMessage(requestError, "Unable to load audit events."));
      }
    }).finally(() => {
      if (!cancelled) setIsLoading(false);
    });

    return () => { cancelled = true; };
  }, [page, reloadKey, resourceType]);

  const firstItem = total === 0 ? 0 : page * PAGE_SIZE + 1;
  const lastItem = Math.min((page + 1) * PAGE_SIZE, total);

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-black tracking-tight text-gray-900">
            <ListChecks className="h-6 w-6 text-primary-600" />
            Audit Events
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Recorded application events available to administrator and auditor accounts.
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm font-medium text-gray-700">
          Resource
          <select
            value={resourceType}
            onChange={(event) => {
              setPage(0);
              setResourceType(event.target.value);
            }}
            className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-200"
          >
            <option value="all">All resources</option>
            {RESOURCE_TYPES.map((resource) => (
              <option key={resource} value={resource}>{formatLabel(resource)}</option>
            ))}
          </select>
        </label>
      </header>

      <section className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4" aria-label="Audit log limitations">
        <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" />
        <p className="text-sm text-amber-950">
          This page shows event rows recorded by the application. It omits free-form details,
          IP addresses, and user-agent strings. The database table is not tamper-evident and
          does not establish regulatory compliance.
        </p>
      </section>

      {error ? (
        <div role="alert" className="flex items-start justify-between gap-4 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          <span className="flex items-start gap-2"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />{error}</span>
          <button
            type="button"
            onClick={() => setReloadKey((value) => value + 1)}
            className="shrink-0 font-semibold underline underline-offset-2"
          >
            Retry
          </button>
        </div>
      ) : (
        <section className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm" aria-label="Recorded audit events">
          {isLoading ? (
            <div role="status" aria-live="polite" className="p-8 text-center text-sm text-gray-500">
              Loading recorded events...
            </div>
          ) : items.length === 0 ? (
            <div className="p-10 text-center">
              <p className="font-semibold text-gray-800">No recorded events</p>
              <p className="mt-1 text-sm text-gray-500">No events match this resource filter.</p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 text-left text-sm">
                  <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
                    <tr>
                      <th scope="col" className="px-5 py-3 font-semibold">Timestamp</th>
                      <th scope="col" className="px-5 py-3 font-semibold">Actor ID</th>
                      <th scope="col" className="px-5 py-3 font-semibold">Action</th>
                      <th scope="col" className="px-5 py-3 font-semibold">Resource</th>
                      <th scope="col" className="px-5 py-3 font-semibold">Resource ID</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {items.map((item) => <AuditEventRow key={item.id} item={item} />)}
                  </tbody>
                </table>
              </div>
              <footer className="flex flex-col gap-3 border-t border-gray-100 px-5 py-3 text-sm text-gray-600 sm:flex-row sm:items-center sm:justify-between">
                <span aria-live="polite">Showing {firstItem}-{lastItem} of {total}</span>
                <div className="flex items-center gap-2 self-end sm:self-auto">
                  <button
                    type="button"
                    onClick={() => setPage((value) => Math.max(0, value - 1))}
                    disabled={page === 0 || isLoading}
                    aria-label="Previous page"
                    className="rounded-lg border border-gray-300 p-2 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setPage((value) => value + 1)}
                    disabled={lastItem >= total || isLoading}
                    aria-label="Next page"
                    className="rounded-lg border border-gray-300 p-2 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </button>
                </div>
              </footer>
            </>
          )}
        </section>
      )}
    </div>
  );
};

const AuditEventRow: React.FC<{ item: AuditEvent }> = ({ item }) => (
  <tr className="align-top hover:bg-gray-50/70">
    <td className="whitespace-nowrap px-5 py-3 text-gray-600">{formatTimestamp(item.timestamp)}</td>
    <td className="max-w-48 break-all px-5 py-3 font-mono text-xs text-gray-600">{item.user_id ?? "System"}</td>
    <td className="px-5 py-3 font-medium capitalize text-gray-900">{formatLabel(item.action)}</td>
    <td className="px-5 py-3 capitalize text-gray-600">{formatLabel(item.resource_type)}</td>
    <td className="max-w-56 break-all px-5 py-3 font-mono text-xs text-gray-500">{item.resource_id ?? "—"}</td>
  </tr>
);
