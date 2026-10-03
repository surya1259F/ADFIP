export function cn(...classes: (string | undefined | null | false)[]) {
  return classes.filter(Boolean).join(' ');
}

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

export function formatTimestamp(ts: string | null | undefined): string {
  if (!ts) return 'N/A';
  const d = new Date(ts);
  if (isNaN(d.getTime())) return 'Invalid Date';
  return d.toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
}

export function formatRelativeTime(ts: string): string {
  const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
  const daysDifference = Math.round(
    (new Date(ts).getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24)
  );
  if (Math.abs(daysDifference) > 30) {
    return formatTimestamp(ts).substring(0, 10);
  }
  return rtf.format(daysDifference, 'day');
}

export function truncateHash(hash: string, chars = 4): string {
  if (!hash) return '';
  if (hash.length <= chars * 2) return hash;
  return `${hash.slice(0, chars)}...${hash.slice(-chars)}`;
}

export function truncateId(id: string, chars = 4): string {
  return truncateHash(id, chars);
}

export function formatConfidence(conf: number | null | undefined): string {
  if (conf == null) return 'Unknown';
  return conf.toFixed(2);
}

export const STATUS_TONES: Record<string, 'neutral' | 'info' | 'success' | 'warning' | 'danger' | 'active'> = {
  QUEUED: 'neutral', RUNNING: 'active', COMPLETED: 'success', FAILED: 'danger', CANCELLED: 'neutral',
  VERIFIED: 'success', UNVERIFIED: 'warning', REVIEW: 'warning', SUPPORTED: 'success', UNSUPPORTED: 'danger',
  PENDING: 'warning', DRAFT: 'neutral', READY: 'success', FINAL: 'success', ACCEPTED: 'success', REJECTED: 'danger', CHALLENGED: 'warning', ACTIVE: 'active', CLOSED: 'neutral', ARCHIVED: 'neutral'
};

export function getStatusTone(status: string): 'neutral' | 'info' | 'success' | 'warning' | 'danger' | 'active' {
  return STATUS_TONES[status?.toUpperCase()] || 'neutral';
}
