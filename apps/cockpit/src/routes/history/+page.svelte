<script lang="ts">
	import type { PageData } from './$types';
	import Shell from '$lib/components/Shell.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import MetricTile from '$lib/components/MetricTile.svelte';
	import EquityChart from '$lib/components/EquityChart.svelte';
	import DataTable from '$lib/components/DataTable.svelte';
	import CalibrationChart from '$lib/components/CalibrationChart.svelte';
	import { fmtInt, fmtNum, fmtPct, fmtUsd, signClass } from '$lib/format';

	let { data }: { data: PageData } = $props();
	const flight = $derived(data.flight);
	const series = $derived(flight?.series);
	const equity = $derived(series?.equity_curve ?? []);
	const fills = $derived(series?.fills ?? []);
	const bins = $derived(series?.calibration_bins ?? []);
	const stats = $derived(flight?.stats ?? {});
	const extra = $derived(flight?.extra ?? {});
	const brier = $derived(
		typeof extra.calibration_brier === 'number' ? extra.calibration_brier : null
	);
	const fillSummary = $derived(series?.fill_summary ?? {});

	const fillRows = $derived(
		[...fills].reverse().map((f) => ({ ...f })) as Record<string, unknown>[]
	);
	const fillBySym = $derived(
		Object.entries(fillSummary.by_symbol ?? {}).map(([symbol, n]) => ({
			symbol,
			n
		})) as Record<string, unknown>[]
	);

	const peak = $derived.by(() => {
		if (!equity.length) return null;
		return Math.max(...equity.map((e) => e.equity_usd));
	});
	const trough = $derived.by(() => {
		if (!equity.length) return null;
		return Math.min(...equity.map((e) => e.equity_usd));
	});
</script>

<Shell
	flight={flight}
	env={data.env}
	pathUsed={data.pathUsed}
	loadedAt={data.loadedAt}
>
	<div class="page">
		<div class="hero">
			<MetricTile
				label="Total Return"
				value={fmtPct(stats.total_return)}
				tone={signClass(stats.total_return)}
				large
			/>
			<MetricTile
				label="Final Equity"
				value={fmtUsd(stats.final_equity_usd)}
				tone="pos"
				large
			/>
			<MetricTile label="Peak Equity" value={fmtUsd(peak)} tone="cyan" large />
			<MetricTile label="Trough Equity" value={fmtUsd(trough)} tone="neg" large />
			<MetricTile
				label="Max DD"
				value={fmtPct(stats.max_drawdown)}
				tone="neg"
				large
			/>
			<MetricTile
				label="Sharpe-like"
				value={fmtNum(stats.sharpe_like, 3)}
				tone="cyan"
				large
			/>
			<MetricTile label="Fills" value={fmtInt(stats.n_fills)} tone="neu" large />
			<MetricTile
				label="Equity pts"
				value={fmtInt(equity.length)}
				sub={series?.meta?.n_equity != null ? 'downsampled if needed' : ''}
				tone="amber"
				large
			/>
		</div>

		<Panel title="Walk-Forward Equity" tag="PAPER PATH" accent="cyan">
			<EquityChart points={equity} height={280} />
			{#snippet footer()}
				Honest equity_cents series from PaperBroker · start
				{fmtUsd(typeof extra.start_equity_usd === 'number' ? extra.start_equity_usd : 100000)}
			{/snippet}
		</Panel>

		<div class="split">
			<Panel title="Fill Blotter" tag={`${fills.length} ROWS`} accent="amber">
				<DataTable
					maxHeight="360px"
					empty="NO FILLS — re-run lacie flight for series"
					columns={[
						{ key: 'date', label: 'DATE' },
						{ key: 'symbol', label: 'SYM' },
						{
							key: 'side',
							label: 'SIDE',
							tone: (r) => (r.side === 'buy' ? 'pos' : 'neg')
						},
						{
							key: 'qty',
							label: 'QTY',
							align: 'right',
							fmt: (v) => fmtInt(Number(v))
						},
						{
							key: 'px',
							label: 'PX',
							align: 'right',
							fmt: (v) => fmtNum(Number(v), 2)
						},
						{
							key: 'notional_usd',
							label: 'NOTIONAL',
							align: 'right',
							fmt: (v) => fmtUsd(Number(v))
						},
						{ key: 'reason', label: 'REASON' }
					]}
					rows={fillRows}
				/>
			</Panel>
			<div class="stack">
				<Panel title="Fills by Symbol" tag="SUMMARY" accent="cyan" compact>
					{#if fillBySym.length}
						<DataTable
							maxHeight="160px"
							columns={[
								{ key: 'symbol', label: 'SYM' },
								{
									key: 'n',
									label: 'N',
									align: 'right',
									fmt: (v) => fmtInt(Number(v))
								}
							]}
							rows={fillBySym}
						/>
						<p class="note mono">
							gross notional {fmtUsd(fillSummary.gross_notional_usd)} · total
							{fmtInt(fillSummary.n_total)}
						</p>
					{:else}
						<p class="pending mono">NO FILL SUMMARY</p>
					{/if}
				</Panel>
				<Panel title="Calibration" tag="RELIABILITY" accent="violet">
					{#if bins.length}
						<CalibrationChart {bins} {brier} />
					{:else}
						<p class="pending mono">NO BINS — series pending</p>
					{/if}
				</Panel>
			</div>
		</div>
	</div>
</Shell>

<style>
	.page {
		padding: var(--gap);
		display: flex;
		flex-direction: column;
		gap: var(--gap);
	}
	.hero {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: var(--gap);
	}
	.split {
		display: grid;
		grid-template-columns: 1.4fr 1fr;
		gap: var(--gap);
	}
	.stack {
		display: flex;
		flex-direction: column;
		gap: var(--gap);
	}
	.note {
		margin: 8px 0 0;
		font-size: 10px;
		color: var(--text-mute);
	}
	.pending {
		color: var(--amber);
		padding: 16px;
		font-size: 11px;
	}
	@media (max-width: 1100px) {
		.hero {
			grid-template-columns: 1fr 1fr;
		}
		.split {
			grid-template-columns: 1fr;
		}
	}
</style>
