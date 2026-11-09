/** Ignore malformed bookmarks while preserving valid server pagination offsets. */
export function pageOffset(value: string | null, limit: number) {
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed >= 0
    ? Math.floor(parsed / limit) * limit
    : 0;
}
