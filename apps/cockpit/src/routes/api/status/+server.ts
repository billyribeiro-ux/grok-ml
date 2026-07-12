import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import {
	loadEarningsResearch,
	loadLatestFlight,
	loadStatusJson,
	listFlights
} from '$lib/server/flight';
import { existsSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

function countJson(dir: string): number {
	if (!existsSync(dir)) return 0;
	try {
		return readdirSync(dir).filter((n) => n.endsWith('.json') && !n.startsWith('._')).length;
	} catch {
		return 0;
	}
}

export const GET: RequestHandler = async () => {
	const { flight, pathUsed, env } = loadLatestFlight();
	const root = '/Volumes/LaCie/Aether/data/raw/fmp';
	const mtf = {
		sp500: {
			eod: countJson(join(root, 'sp500_full/ohlcv_eod')),
			'1hour': countJson(join(root, 'sp500_full/ohlcv_1hour')),
			'15min': countJson(join(root, 'sp500_full/ohlcv_15min')),
			'5min': countJson(join(root, 'sp500_full/ohlcv_5min')),
			'1min': countJson(join(root, 'sp500_full/ohlcv_1min'))
		},
		iwm: {
			eod: countJson(join(root, 'iwm_russell2000/ohlcv_eod')),
			'1hour': countJson(join(root, 'iwm_russell2000/ohlcv_1hour')),
			'15min': countJson(join(root, 'iwm_russell2000/ohlcv_15min')),
			'5min': countJson(join(root, 'iwm_russell2000/ohlcv_5min')),
			'1min': countJson(join(root, 'iwm_russell2000/ohlcv_1min'))
		},
		nasdaq: {
			eod: countJson(join(root, 'nasdaq_full/ohlcv_eod')),
			'1hour': countJson(join(root, 'nasdaq_full/ohlcv_1hour')),
			'15min': countJson(join(root, 'nasdaq_full/ohlcv_15min')),
			'5min': countJson(join(root, 'nasdaq_full/ohlcv_5min')),
			'1min': countJson(join(root, 'nasdaq_full/ohlcv_1min'))
		}
	};
	const earnings = loadEarningsResearch();
	return json({
		env,
		pathUsed,
		loadedAt: new Date().toISOString(),
		status: loadStatusJson(),
		flights: listFlights(12),
		mtf,
		earnings: {
			specialists: earnings.specialists,
			summaries: earnings.summaries
		},
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
