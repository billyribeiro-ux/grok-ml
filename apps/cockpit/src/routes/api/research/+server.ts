import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { readFileSync, existsSync } from 'node:fs';

const ROOT = '/Volumes/LaCie/Aether/data/processed/research';

function read(name: string): unknown {
	const p = `${ROOT}/${name}`;
	if (!existsSync(p)) return null;
	try {
		return JSON.parse(readFileSync(p, 'utf8'));
	} catch {
		return null;
	}
}

/** Aggregate research artifacts for tools / cockpit refresh. */
export const GET: RequestHandler = async () => {
	return json({
		loadedAt: new Date().toISOString(),
		summary: read('research_summary.json'),
		leaderboard: read('flight_leaderboard.json'),
		index: read('index.json'),
		walkforward:
			read('latest_walkforward_hybrid_conf58.json') ??
			read('latest_walkforward_hybrid_sector_mission.json') ??
			read('latest_walkforward.json'),
		riskSweep:
			read('latest_risk_sweep_hybrid_sector_mission.json') ?? read('latest_risk_sweep.json'),
		horizon: read('latest_horizon_compare.json'),
		calByRegime: read('latest_calibration_by_regime.json'),
		confPositionGrid: read('latest_conf_position_grid.json'),
		purgeTrainSensitivity: read('latest_purge_train_sensitivity.json')
	});
};
