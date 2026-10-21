export function formatTime(value?: string | null): string {
  if (!value) return '—';
  return value.replace('T', ' ').replace(/(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$/, '').slice(0, 16);
}

export function shortMemoryId(id: string): string {
  return id.length > 14 ? `…${id.slice(-8)}` : id;
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function countByValidity(
  validity: Array<{ status: string }>,
): Record<string, number> {
  return validity.reduce<Record<string, number>>((acc, item) => {
    acc[item.status] = (acc[item.status] ?? 0) + 1;
    return acc;
  }, {});
}
