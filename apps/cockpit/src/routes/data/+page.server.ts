import type { PageServerLoad } from './$types';
import {
	HONEST_GAPS,
	loadLatestFlight,
	loadResearchIndex,
	loadStatusJson,
	listFlights
} from '$lib/server/flight';

export const load: PageServerLoad = async () => {
	const { flight, pathUsed, env } = loadLatestFlight();
	const status = loadStatusJson();
	const flights = listFlights(24);
	return {
		flight,
		pathUsed,
		gaps: HONEST_GAPS,
		env,
		loadedAt: new Date().toISOString(),
		status,
		flights,
		researchIndex: loadResearchIndex()
	};
};
