import type { PageServerLoad } from './$types';
import {
	HONEST_GAPS,
	loadLatestFlight,
	loadResearchIndex,
	loadStatusJson,
	listFlights
} from '$lib/server/flight';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

function countJson(dir: string): number {
	if (!existsSync(dir)) return 0;
	try {
		return readdirSync(dir).filter((n) => !n.startsWith('._') && n.endsWith('.json')).length;
	} catch {
		return 0;
	}
}

function readJson(path: string): Record<string, unknown> | null {
	try {
		if (!existsSync(path)) return null;
		return JSON.parse(readFileSync(path, 'utf8')) as Record<string, unknown>;
	} catch {
		return null;
	}
}

export const load: PageServerLoad = async () => {
	const { flight, pathUsed, env } = loadLatestFlight();
	const status = loadStatusJson();
	const flights = listFlights(24);
	const root = '/Volumes/LaCie/Aether/data/raw/fmp';
	const mtf = {
		sp500: {
			eod: countJson(join(root, 'sp500_full/ohlcv_eod')),
			'1hour': countJson(join(root, 'sp500_full/ohlcv_1hour')),
			'15min': countJson(join(root, 'sp500_full/ohlcv_15min')),
			'5min': countJson(join(root, 'sp500_full/ohlcv_5min')),
			'1min': countJson(join(root, 'sp500_full/ohlcv_1min')),
			target: 503
		},
		iwm: {
			eod: countJson(join(root, 'iwm_russell2000/ohlcv_eod')),
			'1hour': countJson(join(root, 'iwm_russell2000/ohlcv_1hour')),
			'15min': countJson(join(root, 'iwm_russell2000/ohlcv_15min')),
			'5min': countJson(join(root, 'iwm_russell2000/ohlcv_5min')),
			'1min': countJson(join(root, 'iwm_russell2000/ohlcv_1min')),
			target: 1972
		},
		nasdaq: {
			eod: countJson(join(root, 'nasdaq_full/ohlcv_eod')),
			'1hour': countJson(join(root, 'nasdaq_full/ohlcv_1hour')),
			'15min': countJson(join(root, 'nasdaq_full/ohlcv_15min')),
			'5min': countJson(join(root, 'nasdaq_full/ohlcv_5min')),
			'1min': countJson(join(root, 'nasdaq_full/ohlcv_1min')),
			target: 14213
		}
	};
	const ready = readJson('/Volumes/LaCie/Aether/data/processed/research/ready_snapshot.json');
	const researchRoot = '/Volumes/LaCie/Aether/data/processed/research';
	const pre8 = {
		sp500: readJson(join(researchRoot, 'pre8_backtest_sp500.json')),
		iwm: readJson(join(researchRoot, 'pre8_backtest_iwm.json')),
		nasdaq: readJson(join(researchRoot, 'pre8_backtest_nasdaq.json'))
	};
	const pre8Grid = readJson(join(researchRoot, 'pre8_threshold_grid.json'));
	const mtfResearch: Record<string, Record<string, unknown> | null> = {};
	for (const univ of ['sp500', 'iwm', 'nasdaq'] as const) {
		for (const iv of ['1hour', '15min', '5min', '1min'] as const) {
			for (const lab of ['y_up_1', 'y_up_5'] as const) {
				const key = `${univ}_${iv}_${lab}`;
				mtfResearch[key] = readJson(join(researchRoot, `mtf_research_${univ}_${iv}_${lab}.json`));
			}
		}
	}
	return {
		flight,
		pathUsed,
		gaps: HONEST_GAPS,
		env,
		loadedAt: new Date().toISOString(),
		status,
		flights,
		researchIndex: loadResearchIndex(),
		mtf,
		ready,
		pre8,
		pre8Grid,
		mtfResearch
	};
};
