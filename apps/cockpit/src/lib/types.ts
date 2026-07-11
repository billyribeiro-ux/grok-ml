/** Telemetry contract from aether.engine.telemetry — never invent fields client-side. */

export type FlightReport = {
	name: string;
	written_at: string;
	source: string;
	symbols: string[];
	stats: FlightStats;
	extra?: FlightExtra;
	laws?: FlightLaws;
	series?: FlightSeries;
};

export type FlightStats = {
	total_return?: number | null;
	ann_vol?: number | null;
	sharpe_like?: number | null;
	max_drawdown?: number | null;
	n_fills?: number | null;
	n_signals?: number | null;
	n_stand_down?: number | null;
	n_actionable_signals?: number | null;
	n_rejections?: number | null;
	final_equity_usd?: number | null;
	[key: string]: number | string | null | undefined;
};

export type FlightExtra = {
	train_frac?: number | null;
	cut_date?: string | null;
	calibration_brier?: number | null;
	calibration_n?: number | null;
	train_rows?: number | null;
	test_rows?: number | null;
	start_equity_usd?: number | null;
	n_feature_rows?: number | null;
	n_oos_feature_rows?: number | null;
	regime_daily?: Record<string, unknown>[];
	[key: string]: number | string | null | undefined | Record<string, unknown>[];
};

export type FlightLaws = {
	L0_truth?: boolean;
	note?: string;
	[key: string]: unknown;
};

export type EquityPoint = {
	date: string;
	equity_usd: number;
	equity_cents: number;
	cash_usd?: number | null;
	n_pos?: number | null;
	day_pnl_usd?: number | null;
	drawdown?: number | null;
};

export type FillRow = {
	date: string;
	symbol: string;
	side: string;
	qty: number;
	px: number;
	reason: string;
	notional_usd?: number;
};

export type SignalRow = {
	date: string;
	symbol: string;
	side: string;
	mode: string;
	confidence: number;
	expected_edge: number;
	stop_pct: number;
	target_pct: number;
	size_fraction: number;
	reason: string;
	p_up?: number | null;
};

export type RejectionRow = {
	date: string;
	symbol?: string | null;
	reason?: string | null;
};

export type CalibrationBin = {
	lo: number;
	hi: number;
	n: number;
	avg_p: number | null;
	avg_y: number | null;
};

export type OhlcBar = {
	date: string;
	open?: number;
	high?: number;
	low?: number;
	close: number;
	volume?: number;
	ret_1d?: number;
	px_vs_sma20?: number;
	p_up?: number;
	regime_uncertainty?: number;
	breadth_integrity?: number;
};

export type SignalSummary = {
	by_mode?: Record<string, number>;
	by_side?: Record<string, number>;
	by_symbol?: Record<string, number>;
	n_total?: number;
	n_blotter?: number;
	truncated?: boolean;
};

export type SeriesMeta = {
	n_equity?: number;
	n_fills_payload?: number;
	n_fills_total?: number;
	n_signals_payload?: number;
	n_signals_total?: number;
	n_rejections_payload?: number;
	n_rejections_total?: number;
	ohlc_symbols?: string[];
};

export type FeatureWeight = {
	feature: string;
	weight: number;
	abs_weight: number;
	mean?: number;
	std?: number;
	logit_per_std?: number;
};

export type FillSummary = {
	by_symbol?: Record<string, number>;
	by_side?: Record<string, number>;
	by_reason?: Record<string, number>;
	n_total?: number;
	gross_notional_usd?: number;
};

export type FlightSeries = {
	equity_curve?: EquityPoint[];
	fills?: FillRow[];
	fill_summary?: FillSummary;
	signals?: SignalRow[];
	signal_summary?: SignalSummary;
	rejections?: RejectionRow[];
	rejection_summary?: Record<string, number>;
	calibration_bins?: CalibrationBin[];
	feature_weights?: FeatureWeight[];
	model?: Record<string, unknown>;
	ohlc?: Record<string, OhlcBar[]>;
	meta?: SeriesMeta;
};

export type CockpitLoad = {
	flight: FlightReport | null;
	pathUsed: string | null;
	gaps: string[];
	env: 'SIM' | 'PAPER' | 'OFFLINE';
	loadedAt: string;
};
