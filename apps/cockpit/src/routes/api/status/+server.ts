import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { loadLatestFlight, loadStatusJson, listFlights } from '$lib/server/flight';

export const GET: RequestHandler = async () => {
	const { flight, pathUsed, env } = loadLatestFlight();
	return json({
		env,
		pathUsed,
		loadedAt: new Date().toISOString(),
		status: loadStatusJson(),
		flights: listFlights(12),
		telemetry: {
			name: flight?.name ?? null,
			written_at: flight?.written_at ?? null,
			hasSeries: !!flight?.series,
			nEquity: flight?.series?.equity_curve?.length ?? 0,
			nWeights: flight?.series?.feature_weights?.length ?? 0,
			stats: flight?.stats ?? null
		}
	});
};
