/**
 * MedFusion AI — Clinical Review & Validation History List
 */

import React from "react";
import { UserCheck, MessageSquare, Clock, CheckCircle2 } from "lucide-react";
import { ClinicalReviewResponse, ReviewDecision } from "../../types";
import { ReviewDecisionBadge, UserRoleBadge } from "../common/Badge";

interface ReviewHistoryListProps {
  reviews: ClinicalReviewResponse[];
}

export const ReviewHistoryList: React.FC<ReviewHistoryListProps> = ({ reviews }) => {
  if (!reviews || reviews.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-gray-200 bg-white p-6 text-center text-gray-400">
        <UserCheck className="mx-auto h-8 w-8 text-gray-300" />
        <p className="mt-2 text-xs font-semibold text-gray-500">
          No Clinical Reviews Recorded Yet
        </p>
        <p className="text-[11px] text-gray-400">
          Supervising clinicians or radiologists can validate AI predictions to establish concordance audit trails.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {reviews.map((rev) => (
        <div
          key={rev.id}
          className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm transition-all hover:border-gray-300"
        >
          {/* Header Row */}
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 pb-2.5">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary-100 text-primary-700 font-bold text-xs">
                {rev.reviewer?.full_name ? rev.reviewer.full_name[0] : "D"}
              </div>
              <div>
                <span className="text-xs font-bold text-gray-900">
                  {rev.reviewer?.full_name || "Licensed Medical Reviewer"}
                </span>
                {rev.reviewer?.department && (
                  <span className="ml-1.5 text-[10px] text-gray-400">
                    &bull; {rev.reviewer.department}
                  </span>
                )}
              </div>
              {rev.reviewer?.role && <UserRoleBadge role={rev.reviewer.role} />}
            </div>

            <div className="flex items-center gap-2">
              <ReviewDecisionBadge decision={rev.decision} />
              <span className="flex items-center gap-1 text-[10px] text-gray-400">
                <Clock className="h-3 w-3" />
                {new Date(rev.created_at).toLocaleString()}
              </span>
            </div>
          </div>

          {/* Body Content */}
          <div className="mt-3 space-y-2 text-xs">
            {rev.decision === ReviewDecision.MODIFY && rev.modified_diagnosis && (
              <div className="rounded-lg bg-amber-50/60 p-2.5 border border-amber-100">
                <span className="font-bold text-amber-900">Revised Diagnosis: </span>
                <span className="text-amber-950 font-semibold">{rev.modified_diagnosis}</span>
              </div>
            )}

            {rev.clinical_notes && (
              <div className="flex items-start gap-2 text-gray-700">
                <MessageSquare className="h-3.5 w-3.5 text-gray-400 flex-shrink-0 mt-0.5" />
                <p className="italic text-gray-600 leading-relaxed">&ldquo;{rev.clinical_notes}&rdquo;</p>
              </div>
            )}

            <div className="flex items-center justify-between text-[10px] text-gray-400 pt-1">
              <span>Review ID: <code className="font-mono">{rev.id.slice(0, 8)}...</code></span>
              <span className="inline-flex items-center gap-1 text-emerald-600 font-semibold">
                <CheckCircle2 className="h-3 w-3" /> Signed &amp; Concordance Tracked
              </span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};
