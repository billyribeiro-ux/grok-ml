import type { PageServerLoad } from './$types';
import {
	HONEST_GAPS,
	loadAllWalkforwards,
	loadFlightLeaderboard,
	loadLatestFlight,
	loadResearch
} from '$lib/server/flight';

export const load: PageServerLoad = async () => {
	const { flight, pathUsed, env } = loadLatestFlight();
	return {
		flight,
		pathUsed,
		gaps: HONEST_GAPS,
		env,
		loadedAt: new Date().toISOString(),
		walkforward: loadResearch('walkforward'),
		walkforwards: loadAllWalkforwards(),
		riskSweep: loadResearch('risk_sweep'),
		horizon: loadResearch('horizon_compare'),
		leaderboard: loadFlightLeaderboard(),
		calByRegime: loadResearch('calibration_by_regime'),
		confPositionGrid: loadResearch('conf_position_grid'),
		researchSummary: loadResearch('research_summary'),
		purgeTrainSensitivity: loadResearch('purge_train_sensitivity')
	};
};
