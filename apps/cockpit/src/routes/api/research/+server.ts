import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

const RESEARCH = '/Volumes/LaCie/Aether/data/processed/research';

function readJson(path: string): unknown | null {
	try {
		if (!existsSync(path)) return null;
		return JSON.parse(readFileSync(path, 'utf8'));
	} catch {
		return null;
	}
}

export const GET: RequestHandler = async ({ url }) => {
	const name = url.searchParams.get('name');
	if (name) {
		// safe basename only
		const safe = name.replace(/[^a-zA-Z0-9_\-.]/g, '');
		const path = join(RESEARCH, safe.endsWith('.json') ? safe : `${safe}.json`);
		const data = readJson(path);
		if (!data) return json({ error: 'not found', name: safe }, { status: 404 });
		return json({ name: safe, data });
	}

	const files = existsSync(RESEARCH)
		? readdirSync(RESEARCH).filter(
				(n) => n.endsWith('.json') && !n.startsWith('._') && !n.includes('oos')
			)
		: [];

	const specialists = files
		.filter((n) => n.startsWith('earnings_specialist_'))
		.map((n) => ({ name: n, data: readJson(join(RESEARCH, n)) }));

	const mtf = files
		.filter((n) => n.startsWith('mtf_research_'))
		.map((n) => ({ name: n, data: readJson(join(RESEARCH, n)) }));

	return json({
		loadedAt: new Date().toISOString(),
		ready: readJson(join(RESEARCH, 'ready_snapshot.json')),
		index: readJson(join(RESEARCH, 'index.json')),
		specialists,
		mtfResearch: mtf,
		fileCount: files.length
	});
};
