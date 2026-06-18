type ExportRow = {
  uid: string;
  status: string;
  columns: string[];
  source: string[];
  target: string[];
};

const escapeCsv = (v: string) => {
  if (/[",\n]/.test(v)) return `"${v.replace(/"/g, '""')}"`;
  return v;
};

export const downloadSnippetCsv = (rows: ExportRow[], columns: string[], filename: string) => {
  const header = ['uid', 'status', ...columns.flatMap((c) => [`source:${c}`, `target:${c}`])];
  const lines = [
    header.map(escapeCsv).join(','),
    ...rows.map((r) => [
      r.uid,
      r.status,
      ...columns.flatMap((_, i) => [r.source[i] ?? '', r.target[i] ?? '']),
    ].map(escapeCsv).join(',')),
  ];
  const blob = new Blob(['\ufeff', lines.join('\n')], { type: 'text/csv;charset=utf-8' });
  triggerDownload(blob, filename.endsWith('.csv') ? filename : `${filename}.csv`);
};

export const downloadSnippetXlsx = (rows: ExportRow[], columns: string[], filename: string) => {
  // Excel opens UTF-8 CSV saved as .xlsx alternative — use .csv with excel mime for zero deps
  downloadSnippetCsv(rows, columns, filename.replace(/\.xlsx?$/i, '') + '.csv');
};

export const downloadSnippetPdf = (rows: ExportRow[], columns: string[], title: string) => {
  const html = `<!DOCTYPE html><html><head><title>${title}</title>
<style>body{font-family:monospace;font-size:11px}table{border-collapse:collapse;width:100%}
th,td{border:1px solid #ccc;padding:4px 6px}th{background:#f1f5f9}.mismatch{background:#fee2e2}
.extra{background:#fff7ed}</style></head><body><h2>${title}</h2><table><thead><tr>
<th>UID</th><th>Status</th>${columns.map((c) => `<th colspan="2">${c}</th>`).join('')}
</tr><tr><th></th><th></th>${columns.map(() => '<th>Src</th><th>Tgt</th>').join('')}</tr></thead><tbody>
${rows.map((r) => `<tr class="${r.status !== 'match' ? (r.status === 'mismatch' ? 'mismatch' : 'extra') : ''}">
<td>${r.uid}</td><td>${r.status}</td>
${columns.map((_, i) => `<td>${r.source[i] ?? ''}</td><td>${r.target[i] ?? ''}</td>`).join('')}
</tr>`).join('')}</tbody></table></body></html>`;
  const w = window.open('', '_blank');
  if (!w) return;
  w.document.write(html);
  w.document.close();
  w.focus();
  w.print();
};

const triggerDownload = (blob: Blob, filename: string) => {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
};
