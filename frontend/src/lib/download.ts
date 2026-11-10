function saveBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function downloadJson(filename: string, data: unknown) {
  saveBlob(filename, new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
}

export function downloadText(filename: string, content: string, mimeType = "text/plain;charset=utf-8") {
  saveBlob(filename, new Blob([content], { type: mimeType }));
}

export function downloadCsv(filename: string, rows: string[][]) {
  const escape = (value: string) => `"${value.replace(/"/g, '""')}"`;
  const content = rows.map((row) => row.map(escape).join(",")).join("\n");
  downloadText(filename, `\uFEFF${content}`, "text/csv;charset=utf-8");
}

export function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
