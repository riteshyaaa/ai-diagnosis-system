/**
 * MedFusion AI — Status & Category Badges
 */

import React from "react";
import clsx from "clsx";
import { CaseStatus, ConfidenceBand, ReviewDecision, UserRole } from "../../types";

export interface BadgeProps {
  children: React.ReactNode;
  variant?:
    | "default"
    | "success"
    | "warning"
    | "danger"
    | "info"
    | "neutral"
    | "purple";
  size?: "sm" | "md";
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = "default",
  size = "sm",
  className,
}) => {
  const variantStyles = {
    default: "bg-gray-100 text-gray-800 ring-gray-600/20",
    success: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    warning: "bg-amber-50 text-amber-800 ring-amber-600/20",
    danger: "bg-rose-50 text-rose-700 ring-rose-600/20",
    info: "bg-blue-50 text-blue-700 ring-blue-600/20",
    neutral: "bg-slate-100 text-slate-700 ring-slate-500/20",
    purple: "bg-purple-50 text-purple-700 ring-purple-600/20",
  };

  const sizeStyles = {
    sm: "px-2 py-0.5 text-xs font-medium",
    md: "px-2.5 py-1 text-xs font-semibold",
  };

  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full ring-1 ring-inset capitalize",
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
    >
      {children}
    </span>
  );
};

export const CaseStatusBadge: React.FC<{ status: CaseStatus | string }> = ({ status }) => {
  switch (status) {
    case CaseStatus.DRAFT:
      return <Badge variant="neutral">Draft</Badge>;
    case CaseStatus.SUBMITTED:
      return <Badge variant="info">Submitted</Badge>;
    case CaseStatus.PROCESSING:
      return <Badge variant="purple">Processing</Badge>;
    case CaseStatus.COMPLETED:
      return <Badge variant="success">Completed</Badge>;
    case CaseStatus.REVIEWED:
      return <Badge variant="success">Reviewed (MD)</Badge>;
    case CaseStatus.ARCHIVED:
      return <Badge variant="default">Archived</Badge>;
    default:
      return <Badge>{status}</Badge>;
  }
};

export const ConfidenceBandBadge: React.FC<{ band: ConfidenceBand | string }> = ({ band }) => {
  switch (band?.toLowerCase()) {
    case ConfidenceBand.HIGH:
    case "high":
      return <Badge variant="success">High Confidence</Badge>;
    case ConfidenceBand.MODERATE:
    case "moderate":
      return <Badge variant="warning">Moderate Confidence</Badge>;
    case ConfidenceBand.LOW:
    case "low":
      return <Badge variant="danger">Low Confidence</Badge>;
    case ConfidenceBand.ABSTAIN:
    case "abstain":
      return <Badge variant="danger">Abstained (Safety)</Badge>;
    default:
      return <Badge>{band}</Badge>;
  }
};

export const ReviewDecisionBadge: React.FC<{ decision: ReviewDecision | string }> = ({ decision }) => {
  switch (decision?.toLowerCase()) {
    case ReviewDecision.ACCEPT:
    case "accept":
      return <Badge variant="success">Accepted</Badge>;
    case ReviewDecision.MODIFY:
    case "modify":
      return <Badge variant="warning">Modified</Badge>;
    case ReviewDecision.REJECT:
    case "reject":
      return <Badge variant="danger">Rejected</Badge>;
    default:
      return <Badge>{decision}</Badge>;
  }
};

export const UserRoleBadge: React.FC<{ role: UserRole | string }> = ({ role }) => {
  switch (role) {
    case UserRole.CLINICIAN:
      return <Badge variant="info">Clinician</Badge>;
    case UserRole.RADIOLOGIST:
      return <Badge variant="purple">Radiologist</Badge>;
    case UserRole.ADMIN:
      return <Badge variant="warning">Admin</Badge>;
    case UserRole.AUDITOR:
      return <Badge variant="neutral">Compliance Auditor</Badge>;
    default:
      return <Badge>{role}</Badge>;
  }
};
