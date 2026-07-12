import { readFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import type { FlightReport } from '$lib/types';

export const HONEST_GAPS = [
	'TICK / ADD / VOLD / TRIN — classic breadth not on FMP (Schwab/TOS later)',
	'Equity put/call CPC — not on FMP',
	'SKEW index — not on FMP',
	'Live broker fills / order routing — Schwab later',
	'Intraday TBBO microstructure — Databento partial; no new spend without re-quote',
	'Live quotes — cockpit is telemetry-bound, not a quote vendor'
];

const LACIE_TEL = '/Volumes/LaCie/Aether/data/processed/telemetry';
const LACIE_STATUS = '/Volumes/LaCie/Aether/data/processed/status/latest_status.json';

export function flightCandidates(cwd = process.cwd()): string[] {
	return [
		join(LACIE_TEL, 'latest_flight.json'),
		join(cwd, '../../.aether/telemetry/latest_flight.json'),
		join(cwd, '../.aether/telemetry/latest_flight.json'),
		join(cwd, '.aether/telemetry/latest_flight.json'),
		join(cwd, '../../packages/../.aether/telemetry/latest_flight.json')
	];
}

export type FlightListItem = {
	name: string;
	path: string;
	bytes: number;
	mtime: string;
};

export function listFlights(limit = 20): FlightListItem[] {
	const dirs = [LACIE_TEL, join(process.cwd(), '../../.aether/telemetry')];
	const items: FlightListItem[] = [];
	for (const dir of dirs) {
		if (!existsSync(dir)) continue;
		for (const name of readdirSync(dir)) {
			if (!name.endsWith('.json') || name.startsWith('._') || name.startsWith('latest'))
				continue;
			const path = join(dir, name);
			try {
				const st = statSync(path);
				items.push({
					name,
					path,
					bytes: st.size,
					mtime: new Date(st.mtimeMs).toISOString()
				});
			} catch {
				/* skip */
			}
		}
		if (items.length) break;
	}
	return items.sort((a, b) => b.mtime.localeCompare(a.mtime)).slice(0, limit);
}

export function loadResearchIndex(): Record<string, unknown> | null {
	return tryReadJsonFile('/Volumes/LaCie/Aether/data/processed/research/index.json');
}

const EARNINGS_RESEARCH = '/Volumes/LaCie/Aether/data/processed/research/earnings_events';
const EARNINGS_ARCHIVE = '/Volumes/LaCie/Aether/data/raw/fmp/earnings_archive';

/** Honest local earnings archive + event-study summaries (no network). */
export function loadEarningsResearch(): {
	summaries: Record<string, Record<string, unknown>>;
	panels: Record<string, { exists: boolean; path: string }>;
	specialists: Record<string, Record<string, unknown>>;
	mtfResearch: Record<string, Record<string, unknown>>;
	meta: Record<string, unknown> | null;
} {
	const summaries: Record<string, Record<string, unknown>> = {};
	for (const u of ['sp500', 'iwm', 'nasdaq'] as const) {
		const p = join(EARNINGS_RESEARCH, `${u}_summary.json`);
		const j = tryReadJsonFile(p);
		if (j) summaries[u] = j;
	}
	const panels: Record<string, { exists: boolean; path: string }> = {};
	for (const u of ['all', 'sp500', 'iwm', 'nasdaq'] as const) {
		const p = join(EARNINGS_ARCHIVE, 'panels', `${u}_2018_20260710.parquet`);
		panels[u] = { exists: existsSync(p), path: p };
	}
	const researchRoot = '/Volumes/LaCie/Aether/data/processed/research';
	const specialists: Record<string, Record<string, unknown>> = {};
	for (const u of ['sp500', 'iwm'] as const) {
		const j = tryReadJsonFile(join(researchRoot, `earnings_specialist_${u}.json`));
		if (j) specialists[u] = j;
	}
	const mtfResearch: Record<string, Record<string, unknown>> = {};
	for (const name of [
		'mtf_research_sp500_15min_y_up_5.json',
		'mtf_research_sp500_1hour_y_up_5.json'
	]) {
		const j = tryReadJsonFile(join(researchRoot, name));
		if (j) mtfResearch[name.replace('mtf_research_', '').replace('.json', '')] = j;
	}
	return {
		summaries,
		panels,
		specialists,
		mtfResearch,
		meta: tryReadJsonFile(join(EARNINGS_ARCHIVE, 'meta.json'))
	};
}

export function loadFlightLeaderboard(): Record<string, unknown> | null {
	return tryReadJsonFile(
		'/Volumes/LaCie/Aether/data/processed/research/flight_leaderboard.json'
	);
}

export function loadStatusJson(): Record<string, unknown> | null {
	const candidates = [
		LACIE_STATUS,
		join(process.cwd(), '../../.aether/status/latest_status.json')
	];
	for (const p of candidates) {
		try {
			if (!existsSync(p)) continue;
			return JSON.parse(readFileSync(p, 'utf8')) as Record<string, unknown>;
		} catch {
			/* next */
		}
	}
	return null;
}

function tryReadJsonFile(path: string): Record<string, unknown> | null {
	try {
		if (!existsSync(path)) return null;
		return JSON.parse(readFileSync(path, 'utf8')) as Record<string, unknown>;
	} catch {
		return null;
	}
}

export function loadResearch(
	kind: 'walkforward' | 'risk_sweep' | 'horizon_compare' | string
): Record<string, unknown> | null {
	const map: Record<string, string[]> = {
		walkforward: [
			'latest_walkforward_hybrid_conf58.json',
			'latest_walkforward_hybrid_sector_mission.json',
			'latest_walkforward_mission_best_risk.json',
			'latest_walkforward_mega_plus_bench.json',
			'latest_walkforward_custom.json',
			'latest_walkforward.json'
		],
		risk_sweep: [
			'latest_risk_sweep_hybrid_sector_mission.json',
			'latest_risk_sweep.json'
		],
		horizon_compare: ['latest_horizon_compare.json'],
		calibration_by_regime: ['latest_calibration_by_regime.json'],
		conf_position_grid: ['latest_conf_position_grid.json'],
		research_summary: ['research_summary.json'],
		purge_train_sensitivity: ['latest_purge_train_sensitivity.json']
	};
	const names = map[kind] ?? [`latest_${kind}.json`];
	const dirs = [
		'/Volumes/LaCie/Aether/data/processed/research',
		join(process.cwd(), '../../.aether/research')
	];
	for (const dir of dirs) {
		for (const n of names) {
			const j = tryReadJsonFile(join(dir, n));
			if (j) return j;
		}
	}
	return null;
}

export function loadAllWalkforwards(): Record<string, Record<string, unknown>> {
	const dirs = [
		'/Volumes/LaCie/Aether/data/processed/research',
		join(process.cwd(), '../../.aether/research')
	];
	const out: Record<string, Record<string, unknown>> = {};
	for (const dir of dirs) {
		if (!existsSync(dir)) continue;
		for (const name of readdirSync(dir)) {
			if (!name.startsWith('latest_walkforward') || !name.endsWith('.json')) continue;
			if (name.startsWith('._')) continue;
			const j = tryReadJsonFile(join(dir, name));
			if (j) out[name.replace('latest_walkforward_', '').replace('.json', '')] = j;
		}
		if (Object.keys(out).length) break;
	}
	return out;
}

export function tryReadFlight(path: string): FlightReport | null {
	try {
		if (!existsSync(path)) return null;
		return JSON.parse(readFileSync(path, 'utf8')) as FlightReport;
	} catch {
		return null;
	}
}

export function loadLatestFlight(cwd = process.cwd()): {
	flight: FlightReport | null;
	pathUsed: string | null;
	env: 'SIM' | 'PAPER' | 'OFFLINE';
} {
	let flight: FlightReport | null = null;
	let pathUsed: string | null = null;
	for (const p of flightCandidates(cwd)) {
		flight = tryReadFlight(p);
		if (flight) {
			pathUsed = p;
			break;
		}
	}
	const source = flight?.source ?? '';
	const env: 'SIM' | 'PAPER' | 'OFFLINE' = !flight
		? 'OFFLINE'
		: source.toLowerCase().includes('mock')
			? 'SIM'
			: 'PAPER';
	return { flight, pathUsed, env };
}

/**
 * Load a named flight for cockpit compare.
 * Aliases: mission|latest → latest_flight.json
 *          recommended → recommended_hybrid_plus_mega_c58_p3.json (then older aliases)
 */
export function loadNamedFlight(
	name: string | null | undefined,
	cwd = process.cwd()
): { flight: FlightReport | null; pathUsed: string | null; env: 'SIM' | 'PAPER' | 'OFFLINE' } {
	const key = (name ?? '').trim().toLowerCase();
	if (!key || key === 'mission' || key === 'latest') {
		return loadLatestFlight(cwd);
	}

	const candidates: string[] = [];
	if (key === 'recommended' || key === 'rec' || key === 'research') {
		candidates.push(
			join(LACIE_TEL, 'recommended_hybrid_plus_mega_c58_p3_y20.json'),
			join(LACIE_TEL, 'recommended_hybrid_plus_mega_c58_p3.json'),
			join(LACIE_TEL, 'recommended_hybrid_c58_pos3.json'),
			join(LACIE_TEL, 'recommended_hybrid_conf58.json')
		);
	} else {
		// exact alias or latest stamped match by name prefix
		candidates.push(join(LACIE_TEL, `${name}.json`));
		if (existsSync(LACIE_TEL)) {
			try {
				const stamped = readdirSync(LACIE_TEL)
					.filter(
						(f) =>
							f.startsWith(`${name}_`) &&
							f.endsWith('.json') &&
							!f.startsWith('._')
					)
					.sort()
					.reverse();
				for (const f of stamped.slice(0, 3)) {
					candidates.push(join(LACIE_TEL, f));
				}
			} catch {
				/* ignore */
			}
		}
	}

	for (const p of candidates) {
		const flight = tryReadFlight(p);
		if (flight) {
			const source = flight.source ?? '';
			const env: 'SIM' | 'PAPER' | 'OFFLINE' = source.toLowerCase().includes('mock')
				? 'SIM'
				: 'PAPER';
			return { flight, pathUsed: p, env };
		}
	}
	return loadLatestFlight(cwd);
}
