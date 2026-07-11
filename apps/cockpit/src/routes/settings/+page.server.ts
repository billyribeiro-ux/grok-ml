import type { PageServerLoad } from './$types';
import { HONEST_GAPS, loadLatestFlight, loadResearch } from '$lib/server/flight';
import { readFileSync, existsSync } from 'node:fs';

function readSummary(): Record<string, unknown> | null {
	const p = '/Volumes/LaCie/Aether/data/processed/research/research_summary.json';
	try {
		if (!existsSync(p)) return null;
		return JSON.parse(readFileSync(p, 'utf8')) as Record<string, unknown>;
	} catch {
		return null;
	}
}

export const load: PageServerLoad = async () => {
	const { flight, pathUsed, env } = loadLatestFlight();
	return {
		flight,
		pathUsed,
		gaps: HONEST_GAPS,
		env,
		loadedAt: new Date().toISOString(),
		researchSummary: readSummary(),
		horizon: loadResearch('horizon_compare')
	};
};
