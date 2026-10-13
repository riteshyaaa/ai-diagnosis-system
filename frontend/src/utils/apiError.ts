function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function apiErrorMessage(error: unknown, fallback: string): string {
  if (isRecord(error) && isRecord(error.response) && isRecord(error.response.data)) {
    const detail = error.response.data.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
  }
  return fallback;
}
