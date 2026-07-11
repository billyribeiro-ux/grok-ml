import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { loadNamedFlight } from '$lib/server/flight';

/** BFF: flight JSON for client refresh. ?name=mission|recommended|<flight_name> */
export const GET: RequestHandler = async ({ url }) => {
	const name = url.searchParams.get('name');
	const { flight, pathUsed, env } = loadNamedFlight(name);
	return json({
		flight,
		pathUsed,
		env,
		requested: name || 'mission',
		loadedAt: new Date().toISOString(),
		hasSeries: !!flight?.series,
		nEquity: flight?.series?.equity_curve?.length ?? 0,
		nSignals: flight?.series?.signals?.length ?? 0,
		nFills: flight?.series?.fills?.length ?? 0
	});
};
