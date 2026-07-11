import type { PageServerLoad } from './$types';
import { HONEST_GAPS, loadLatestFlight } from '$lib/server/flight';

export const load: PageServerLoad = async () => {
	const { flight, pathUsed, env } = loadLatestFlight();
	return {
		flight,
		pathUsed,
		gaps: HONEST_GAPS,
		env,
		loadedAt: new Date().toISOString()
	};
};
