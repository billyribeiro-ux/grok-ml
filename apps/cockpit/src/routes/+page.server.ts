import type { PageServerLoad } from './$types';
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import type { FlightReport } from '$lib/types';

function tryReadJson(path: string): FlightReport | null {
	try {
		if (!existsSync(path)) return null;
		return JSON.parse(readFileSync(path, 'utf8')) as FlightReport;
	} catch {
		return null;
	}
}

export const load: PageServerLoad = async () => {
	const candidates = [
		'/Volumes/LaCie/Aether/data/processed/telemetry/latest_flight.json',
		join(process.cwd(), '../../.aether/telemetry/latest_flight.json'),
		join(process.cwd(), '../.aether/telemetry/latest_flight.json'),
		join(process.cwd(), '.aether/telemetry/latest_flight.json')
	];

	let flight: FlightReport | null = null;
	let pathUsed: string | null = null;
	for (const p of candidates) {
		flight = tryReadJson(p);
		if (flight) {
			pathUsed = p;
			break;
		}
	}

	return {
		flight,
		pathUsed,
		gaps: [
			'TICK / ADD / VOLD / TRIN — not on FMP (Schwab/TOS later)',
			'Equity put/call CPC — not on FMP',
			'SKEW — not on FMP',
			'Live broker fills — Schwab later'
		]
	};
};
