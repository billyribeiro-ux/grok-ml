/** Display formatters — money stays honest; no silent NaN → 0. */

export function fmtPct(v: number | null | undefined, digits = 2): string {
	if (v == null || Number.isNaN(v)) return '—';
	const sign = v > 0 ? '+' : '';
	return `${sign}${(v * 100).toFixed(digits)}%`;
}

export function fmtNum(v: number | null | undefined, digits = 2): string {
	if (v == null || Number.isNaN(v)) return '—';
	return v.toFixed(digits);
}

export function fmtInt(v: number | null | undefined): string {
	if (v == null || Number.isNaN(v)) return '—';
	return Math.round(v).toLocaleString('en-US');
}

export function fmtUsd(v: number | null | undefined): string {
	if (v == null || Number.isNaN(v)) return '—';
	return new Intl.NumberFormat('en-US', {
		style: 'currency',
		currency: 'USD',
		minimumFractionDigits: 2,
		maximumFractionDigits: 2
	}).format(v);
}

export function fmtBrier(v: number | null | undefined): string {
	if (v == null || Number.isNaN(v)) return '—';
	return v.toFixed(4);
}

/** Relative age of telemetry write time. */
export function ageLabel(iso: string | null | undefined, nowMs: number): string {
	if (!iso) return 'NO LINK';
	const t = Date.parse(iso);
	if (Number.isNaN(t)) return 'BAD TS';
	const sec = Math.max(0, Math.floor((nowMs - t) / 1000));
	if (sec < 60) return `${sec}s`;
	if (sec < 3600) return `${Math.floor(sec / 60)}m`;
	if (sec < 86400) return `${Math.floor(sec / 3600)}h`;
	return `${Math.floor(sec / 86400)}d`;
}

export function fmtEtClock(ms: number): string {
	return new Intl.DateTimeFormat('en-US', {
		timeZone: 'America/New_York',
		hour: '2-digit',
		minute: '2-digit',
		second: '2-digit',
		hour12: false
	}).format(new Date(ms));
}

export function fmtEtDate(ms: number): string {
	return new Intl.DateTimeFormat('en-US', {
		timeZone: 'America/New_York',
		weekday: 'short',
		year: 'numeric',
		month: 'short',
		day: '2-digit'
	}).format(new Date(ms));
}

export function fmtUtcIso(iso: string | null | undefined): string {
	if (!iso) return '—';
	const d = Date.parse(iso);
	if (Number.isNaN(d)) return iso;
	return new Date(d).toISOString().replace('.000Z', 'Z');
}

export function signClass(v: number | null | undefined): 'pos' | 'neg' | 'neu' {
	if (v == null || Number.isNaN(v) || v === 0) return 'neu';
	return v > 0 ? 'pos' : 'neg';
}

/** 0–1 clamp for bar widths from ratios. */
export function clamp01(v: number | null | undefined): number {
	if (v == null || Number.isNaN(v)) return 0;
	return Math.min(1, Math.max(0, v));
}
