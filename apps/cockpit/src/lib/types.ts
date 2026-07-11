export type FlightReport = {
	name: string;
	written_at: string;
	source: string;
	symbols: string[];
	stats: Record<string, number | string | null | undefined>;
	extra?: Record<string, unknown>;
	laws?: Record<string, unknown>;
};
