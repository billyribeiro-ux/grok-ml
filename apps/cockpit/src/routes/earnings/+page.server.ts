import type { PageServerLoad } from './$types';
import {
	HONEST_GAPS,
	loadEarningsResearch,
	loadLatestFlight,
	loadStatusJson
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

export const load: PageServerLoad = async () => {
	const { flight, pathUsed, env } = loadLatestFlight();
	const earn = loadEarningsResearch();
	const mtfRoot = '/Volumes/LaCie/Aether/data/raw/fmp';
	const mtf = {
		sp500: {
			eod: countJson(join(mtfRoot, 'sp500_full/ohlcv_eod')),
			'1hour': countJson(join(mtfRoot, 'sp500_full/ohlcv_1hour')),
			'15min': countJson(join(mtfRoot, 'sp500_full/ohlcv_15min')),
			'5min': countJson(join(mtfRoot, 'sp500_full/ohlcv_5min')),
			'1min': countJson(join(mtfRoot, 'sp500_full/ohlcv_1min'))
		},
		iwm: {
			eod: countJson(join(mtfRoot, 'iwm_russell2000/ohlcv_eod')),
			'1hour': countJson(join(mtfRoot, 'iwm_russell2000/ohlcv_1hour')),
			'15min': countJson(join(mtfRoot, 'iwm_russell2000/ohlcv_15min')),
			'5min': countJson(join(mtfRoot, 'iwm_russell2000/ohlcv_5min')),
			'1min': countJson(join(mtfRoot, 'iwm_russell2000/ohlcv_1min'))
		},
		nasdaq: {
			eod: countJson(join(mtfRoot, 'nasdaq_full/ohlcv_eod')),
			'1hour': countJson(join(mtfRoot, 'nasdaq_full/ohlcv_1hour')),
			'15min': countJson(join(mtfRoot, 'nasdaq_full/ohlcv_15min')),
			'5min': countJson(join(mtfRoot, 'nasdaq_full/ohlcv_5min')),
			'1min': countJson(join(mtfRoot, 'nasdaq_full/ohlcv_1min'))
		}
	};

	return {
		flight,
		pathUsed,
		gaps: HONEST_GAPS,
		env,
		loadedAt: new Date().toISOString(),
		status: loadStatusJson(),
		earnings: earn,
		mtf,
		window: '2018-01-01 → 2026-07-10'
	};
};
