/** Shared mission vs research telemetry selection (client-only). */
import type { FlightReport } from '$lib/types';

export type BookId = 'mission' | 'recommended';

let book = $state<BookId>('mission');
let overrideFlight = $state<FlightReport | null>(null);
let overridePath = $state<string | null>(null);
let overrideEnv = $state<'SIM' | 'PAPER' | 'OFFLINE' | null>(null);
let busy = $state(false);

export function getBook() {
	return book;
}
export function getOverrideFlight() {
	return overrideFlight;
}
export function getOverridePath() {
	return overridePath;
}
export function getOverrideEnv() {
	return overrideEnv;
}
export function isBookBusy() {
	return busy;
}

export function resolveFlight(mission: FlightReport | null): FlightReport | null {
	return overrideFlight ?? mission;
}
export function resolvePath(missionPath: string | null): string | null {
	return overridePath ?? missionPath;
}
export function resolveEnv(
	missionEnv: 'SIM' | 'PAPER' | 'OFFLINE'
): 'SIM' | 'PAPER' | 'OFFLINE' {
	return overrideEnv ?? missionEnv;
}

export async function selectBook(next: BookId) {
	if (busy || next === book) return;
	busy = true;
	try {
		const res = await fetch(`/api/flight?name=${next}`);
		if (!res.ok) throw new Error(`flight ${res.status}`);
		const body = (await res.json()) as {
			flight: FlightReport | null;
			pathUsed: string | null;
			env: 'SIM' | 'PAPER' | 'OFFLINE';
		};
		if (next === 'mission') {
			overrideFlight = null;
			overridePath = null;
			overrideEnv = null;
		} else {
			overrideFlight = body.flight;
			overridePath = body.pathUsed;
			overrideEnv = body.env;
		}
		book = next;
	} finally {
		busy = false;
	}
}
