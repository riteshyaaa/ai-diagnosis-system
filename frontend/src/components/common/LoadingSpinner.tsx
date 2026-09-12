/**
 * MedFusion AI — Loading Spinner Component
 */

import React from "react";
import clsx from "clsx";

interface LoadingSpinnerProps {
  size?: "sm" | "md" | "lg";
  className?: string;
  message?: string;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = "md",
  className,
  message,
}) => {
  const sizeClasses = {
    sm: "h-4 w-4 border-2",
    md: "h-8 w-8 border-3",
    lg: "h-12 w-12 border-4",
  };

  return (
    <div className={clsx("flex flex-col items-center justify-center gap-3 p-4", className)}>
      <div
        className={clsx(
          "animate-spin rounded-full border-primary-200 border-t-primary-600",
          sizeClasses[size]
        )}
      />
      {message && <p className="text-xs font-medium text-gray-500 animate-pulse">{message}</p>}
    </div>
  );
};
