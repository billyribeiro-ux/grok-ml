<script lang="ts">
	import type { PageData } from './$types';
	import Shell from '$lib/components/Shell.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import MetricTile from '$lib/components/MetricTile.svelte';
	import DataTable from '$lib/components/DataTable.svelte';
	import { fmtInt, fmtNum, fmtPct, signClass } from '$lib/format';

	let { data }: { data: PageData } = $props();
	const wf = $derived(data.walkforward as Record<string, unknown> | null);
	const sweep = $derived(data.riskSweep as Record<string, unknown> | null);
	const agg = $derived((wf?.aggregate as Record<string, unknown> | undefined) ?? {});
	const folds = $derived(
		((wf?.folds as Record<string, unknown>[]) ?? []).map((f) => {
			const st = (f.stats as Record<string, unknown>) ?? {};
			return {
				fold: f.fold,
				test_start: f.test_start,
				test_end: f.test_end,
				train_rows: f.train_rows,
				test_rows: f.test_rows,
				brier: f.brier,
				total_return: st.total_return,
				sharpe_like: st.sharpe_like,
				max_drawdown: st.max_drawdown,
				n_fills: st.n_fills,
				n_rejections: st.n_rejections
			};
		}) as Record<string, unknown>[]
	);
	const sweepRows = $derived(
		((sweep?.rows as Record<string, unknown>[]) ?? []) as Record<string, unknown>[]
	);
	const horizon = $derived(data.horizon as Record<string, unknown> | null);
	const horizonRows = $derived(
		((horizon?.rows as Record<string, unknown>[]) ?? []) as Record<string, unknown>[]
	);
	const allWf = $derived(
		(data.walkforwards as Record<string, Record<string, unknown>> | undefined) ?? {}
	);
	const wfCards = $derived(
		Object.entries(allWf).map(([tag, body]) => {
			const agg = (body.aggregate as Record<string, unknown>) ?? {};
			return {
				tag,
				mean_return: agg.mean_return,
				mean_sharpe: agg.mean_sharpe,
				pct_positive_folds: agg.pct_positive_folds,
				worst_return: agg.worst_return,
				best_return: agg.best_return,
				n: agg.n_folds_done,
				symbols: ((body.symbols as string[]) ?? []).slice(0, 8).join(' ')
			};
		}) as Record<string, unknown>[]
	);
	const boardRows = $derived(
		(((data.leaderboard as Record<string, unknown> | null)?.flights as Record<
			string,
			unknown
		>[]) ?? []) as Record<string, unknown>[]
	);
	const calReg = $derived(data.calByRegime as Record<string, unknown> | null);
	const calRows = $derived(
		((calReg?.rows as Record<string, unknown>[]) ?? []) as Record<string, unknown>[]
	);
	const confGrid = $derived(data.confPositionGrid as Record<string, unknown> | null);
	const confRows = $derived(
		((confGrid?.rows as Record<string, unknown>[]) ?? []) as Record<string, unknown>[]
	);
	const summary = $derived(data.researchSummary as Record<string, unknown> | null);
	const recommended = $derived(
		(summary?.recommended_book as Record<string, unknown> | undefined) ?? null
	);
	const missionStats = $derived(
		(summary?.mission_stats as Record<string, unknown> | undefined) ?? null
	);
	const purgeSens = $derived(data.purgeTrainSensitivity as Record<string, unknown> | null);
	const purgeRows = $derived(
		((purgeSens?.rows as Record<string, unknown>[]) ?? []) as Record<string, unknown>[]
	);
</script>

<Shell
	flight={data.flight}
	env={data.env}
	pathUsed={data.pathUsed}
	loadedAt={data.loadedAt}
>
	<div class="page">
		{#if summary}
			<div class="hero">
				<MetricTile
					label="Mission book"
					value={String(summary.mission_flight ?? '—')}
					sub={String(summary.mission_window ?? '')}
					tone="cyan"
					large
				/>
				<MetricTile
					label="Mission ret"
					value={fmtPct(missionStats?.total_return as number)}
					tone={signClass(missionStats?.total_return as number)}
					large
				/>
				<MetricTile
					label="Mission sharpe"
					value={fmtNum(missionStats?.sharpe_like as number, 3)}
					tone="amber"
					large
				/>
				<MetricTile
					label="Recommended"
					value={String(recommended?.name ?? '—')}
					sub={recommended
						? `conf ${recommended.min_confidence} · pos ${recommended.max_positions}`
						: ''}
					tone="cyan"
					large
				/>
				<MetricTile
					label="Rec. ret (single)"
					value={fmtPct(
						((recommended?.single_cut as Record<string, unknown> | undefined)
							?.total_return as number) ?? null
					)}
					tone="pos"
					large
				/>
				<MetricTile
					label="Rec. multifold sh"
					value={fmtNum(
						((recommended?.multifold as Record<string, unknown> | undefined)
							?.mean_sharpe as number) ?? null,
						3
					)}
					tone="cyan"
					large
				/>
				<MetricTile
					label="Label winner"
					value={String(summary.label_winner ?? '—')}
					tone="neu"
					large
				/>
				<MetricTile
					label="WF mean ret"
					value={fmtPct(agg.mean_return as number)}
					tone={signClass(agg.mean_return as number)}
					large
				/>
			</div>
		{:else}
			<div class="hero">
				<MetricTile
					label="WF mean return"
					value={fmtPct(agg.mean_return as number)}
					tone={signClass(agg.mean_return as number)}
					large
				/>
				<MetricTile
					label="WF median return"
					value={fmtPct(agg.median_return as number)}
					tone={signClass(agg.median_return as number)}
					large
				/>
				<MetricTile
					label="WF mean sharpe"
					value={fmtNum(agg.mean_sharpe as number, 3)}
					tone="cyan"
					large
				/>
				<MetricTile
					label="% positive folds"
					value={fmtPct(agg.pct_positive_folds as number)}
					tone="amber"
					large
				/>
				<MetricTile
					label="Mean Brier"
					value={fmtNum(agg.mean_brier as number, 4)}
					tone="neu"
					large
				/>
				<MetricTile
					label="Worst fold"
					value={fmtPct(agg.worst_return as number)}
					tone="neg"
					large
				/>
				<MetricTile
					label="Best fold"
					value={fmtPct(agg.best_return as number)}
					tone="pos"
					large
				/>
				<MetricTile
					label="Folds done"
					value={fmtInt(agg.n_folds_done as number)}
					sub={wf ? String(wf.source ?? '') : 'no research yet'}
					tone="cyan"
					large
				/>
			</div>
		{/if}

		{#if purgeRows.length}
			<Panel
				title="Purge × Train-Frac Sensitivity"
				tag="HYBRID C58 POS3"
				accent="amber"
				compact
			>
				<DataTable
					maxHeight="200px"
					columns={[
						{
							key: 'purge_days',
							label: 'PURGE',
							align: 'right',
							fmt: (v) => fmtInt(Number(v))
						},
						{
							key: 'train_frac',
							label: 'TRAIN',
							align: 'right',
							fmt: (v) => fmtNum(Number(v), 2)
						},
						{
							key: 'total_return',
							label: 'RET',
							align: 'right',
							fmt: (v) => fmtPct(Number(v)),
							tone: (r) => signClass(Number(r.total_return))
						},
						{
							key: 'sharpe_like',
							label: 'SHARPE',
							align: 'right',
							fmt: (v) => fmtNum(Number(v), 3)
						},
						{
							key: 'max_drawdown',
							label: 'DD',
							align: 'right',
							fmt: (v) => fmtPct(Number(v)),
							tone: () => 'neg'
						},
						{ key: 'cut', label: 'CUT' },
						{
							key: 'n_fills',
							label: 'FILLS',
							align: 'right',
							fmt: (v) => fmtInt(Number(v))
						}
					]}
					rows={purgeRows}
				/>
			</Panel>
		{/if}

		{#if confRows.length}
			<Panel title="Conf × Position Grid" tag="HYBRID / SECTOR / MEGA" accent="green" compact>
				<DataTable
					maxHeight="260px"
					columns={[
						{ key: 'name', label: 'FLIGHT' },
						{ key: 'universe', label: 'UNIVERSE' },
						{
							key: 'min_confidence',
							label: 'CONF',
							align: 'right',
							fmt: (v) => fmtNum(Number(v), 2)
						},
						{
							key: 'max_positions',
							label: 'POS',
							align: 'right',
							fmt: (v) => fmtInt(Number(v))
						},
						{
							key: 'total_return',
							label: 'RET',
							align: 'right',
							fmt: (v) => fmtPct(Number(v)),
							tone: (r) => signClass(Number(r.total_return))
						},
						{
							key: 'sharpe_like',
							label: 'SHARPE',
							align: 'right',
							fmt: (v) => fmtNum(Number(v), 3)
						},
						{
							key: 'max_drawdown',
							label: 'DD',
							align: 'right',
							fmt: (v) => fmtPct(Number(v)),
							tone: () => 'neg'
						},
						{
							key: 'final_equity_usd',
							label: 'EQ',
							align: 'right',
							fmt: (v) => fmtNum(Number(v), 0)
						},
						{
							key: 'n_fills',
							label: 'FILLS',
							align: 'right',
							fmt: (v) => fmtInt(Number(v))
						}
					]}
					rows={[...confRows].sort(
						(a, b) => Number(b.sharpe_like ?? -9) - Number(a.sharpe_like ?? -9)
					)}
				/>
			</Panel>
		{/if}

		{#if boardRows.length}
			<Panel title="Flight Leaderboard" tag="ALL TELEMETRY" accent="amber" compact>
				<DataTable
					maxHeight="220px"
					columns={[
						{ key: 'name', label: 'FLIGHT' },
						{
							key: 'total_return',
							label: 'RET',
							align: 'right',
							fmt: (v) => fmtPct(Number(v)),
							tone: (r) => signClass(Number(r.total_return))
						},
						{
							key: 'sharpe_like',
							label: 'SHARPE',
							align: 'right',
							fmt: (v) => fmtNum(Number(v), 3)
						},
						{
							key: 'max_drawdown',
							label: 'DD',
							align: 'right',
							fmt: (v) => fmtPct(Number(v)),
							tone: () => 'neg'
						},
						{
							key: 'final_equity_usd',
							label: 'EQ',
							align: 'right',
							fmt: (v) => fmtNum(Number(v), 0)
						},
						{
							key: 'n_symbols',
							label: 'N',
							align: 'right',
							fmt: (v) => fmtInt(Number(v))
						}
					]}
					rows={boardRows.slice(0, 12)}
				/>
			</Panel>
		{/if}

		{#if wfCards.length}
			<Panel title="All Walk-Forward Universes" tag={`${wfCards.length} SETS`} accent="green" compact>
				<DataTable
					maxHeight="200px"
					columns={[
						{ key: 'tag', label: 'SET' },
						{
							key: 'mean_return',
							label: 'MEAN RET',
							align: 'right',
							fmt: (v) => fmtPct(Number(v)),
							tone: (r) => signClass(Number(r.mean_return))
						},
						{
							key: 'mean_sharpe',
							label: 'MEAN SH',
							align: 'right',
							fmt: (v) => fmtNum(Number(v), 3)
						},
						{
							key: 'pct_positive_folds',
							label: '%+',
							align: 'right',
							fmt: (v) => fmtPct(Number(v))
						},
						{
							key: 'worst_return',
							label: 'WORST',
							align: 'right',
							fmt: (v) => fmtPct(Number(v)),
							tone: () => 'neg'
						},
						{
							key: 'best_return',
							label: 'BEST',
							align: 'right',
							fmt: (v) => fmtPct(Number(v)),
							tone: () => 'pos'
						},
						{ key: 'n', label: 'N', align: 'right', fmt: (v) => fmtInt(Number(v)) },
						{ key: 'symbols', label: 'SYMS' }
					]}
					rows={wfCards}
				/>
			</Panel>
		{/if}

		<div class="grid">
			<Panel title="Walk-Forward Folds" tag="PURGED OOS" accent="cyan">
				{#if !folds.length}
					<p class="pending mono">
						Run
						<code>python -m aether.cli walkforward --lacie --folds 5</code>
					</p>
				{:else}
					<DataTable
						maxHeight="420px"
						columns={[
							{ key: 'fold', label: 'F', align: 'right' },
							{ key: 'test_start', label: 'START' },
							{ key: 'test_end', label: 'END' },
							{
								key: 'total_return',
								label: 'RET',
								align: 'right',
								fmt: (v) => fmtPct(Number(v)),
								tone: (r) => signClass(Number(r.total_return))
							},
							{
								key: 'sharpe_like',
								label: 'SHARPE',
								align: 'right',
								fmt: (v) => fmtNum(Number(v), 3)
							},
							{
								key: 'max_drawdown',
								label: 'MAXDD',
								align: 'right',
								fmt: (v) => fmtPct(Number(v)),
								tone: () => 'neg'
							},
							{
								key: 'brier',
								label: 'BRIER',
								align: 'right',
								fmt: (v) => fmtNum(Number(v), 4)
							},
							{
								key: 'n_fills',
								label: 'FILLS',
								align: 'right',
								fmt: (v) => fmtInt(Number(v))
							},
							{
								key: 'n_rejections',
								label: 'REJ',
								align: 'right',
								fmt: (v) => fmtInt(Number(v))
							}
						]}
						rows={folds}
					/>
					{#snippet footer()}
						Expanding train · purge gap · never peeks test into fit
					{/snippet}
				{/if}
			</Panel>

			<Panel title="Risk Sweep (single-cut OOS)" tag="CONFIG GRID" accent="amber">
				{#if !sweepRows.length}
					<p class="pending mono">
						Run
						<code>python -m aether.cli risk-sweep --lacie</code>
					</p>
				{:else}
					<DataTable
						maxHeight="420px"
						columns={[
							{ key: 'id', label: '#', align: 'right' },
							{
								key: 'max_positions',
								label: 'POS',
								align: 'right',
								fmt: (v) => fmtInt(Number(v))
							},
							{
								key: 'min_confidence',
								label: 'CONF',
								align: 'right',
								fmt: (v) => fmtNum(Number(v), 2)
							},
							{
								key: 'max_risk_per_trade',
								label: 'RISK',
								align: 'right',
								fmt: (v) => fmtPct(Number(v))
							},
							{
								key: 'total_return',
								label: 'RET',
								align: 'right',
								fmt: (v) => fmtPct(Number(v)),
								tone: (r) => signClass(Number(r.total_return))
							},
							{
								key: 'sharpe_like',
								label: 'SHARPE',
								align: 'right',
								fmt: (v) => fmtNum(Number(v), 3)
							},
							{
								key: 'max_drawdown',
								label: 'DD',
								align: 'right',
								fmt: (v) => fmtPct(Number(v)),
								tone: () => 'neg'
							},
							{
								key: 'n_fills',
								label: 'FILLS',
								align: 'right',
								fmt: (v) => fmtInt(Number(v))
							},
							{
								key: 'n_rejections',
								label: 'REJ',
								align: 'right',
								fmt: (v) => fmtInt(Number(v))
							}
						]}
						rows={sweepRows}
					/>
					{#snippet footer()}
						Sorted by sharpe_like · research only · not auto-promoted to live risk
					{/snippet}
				{/if}
			</Panel>
		</div>

		<div class="grid">
			<Panel title="Label Horizon Compare" tag="1D · 5D · 20D" accent="violet">
				{#if !horizonRows.length}
					<p class="pending mono">Horizon compare pending — research job running</p>
				{:else}
					<DataTable
						maxHeight="220px"
						columns={[
							{ key: 'label', label: 'LABEL' },
							{
								key: 'total_return',
								label: 'RET',
								align: 'right',
								fmt: (v) => fmtPct(Number(v)),
								tone: (r) => signClass(Number(r.total_return))
							},
							{
								key: 'sharpe_like',
								label: 'SHARPE',
								align: 'right',
								fmt: (v) => fmtNum(Number(v), 3)
							},
							{
								key: 'max_drawdown',
								label: 'DD',
								align: 'right',
								fmt: (v) => fmtPct(Number(v)),
								tone: () => 'neg'
							},
							{
								key: 'brier',
								label: 'BRIER',
								align: 'right',
								fmt: (v) => fmtNum(Number(v), 4)
							},
							{
								key: 'n_fills',
								label: 'FILLS',
								align: 'right',
								fmt: (v) => fmtInt(Number(v))
							}
						]}
						rows={horizonRows}
					/>
				{/if}
			</Panel>
			<Panel title="Calibration × Regime" tag="UNCERTAINTY BUCKETS" accent="cyan">
				{#if !calRows.length}
					<p class="pending mono">Run calibration-by-regime research job</p>
				{:else}
					<p class="meta mono">
						overall Brier {fmtNum(calReg?.overall_brier as number, 4)} · cut
						{String(calReg?.cut ?? '—')}
					</p>
					<DataTable
						maxHeight="240px"
						columns={[
							{ key: 'axis', label: 'AXIS' },
							{ key: 'bucket', label: 'BUCKET' },
							{
								key: 'n',
								label: 'N',
								align: 'right',
								fmt: (v) => fmtInt(Number(v))
							},
							{
								key: 'brier',
								label: 'BRIER',
								align: 'right',
								fmt: (v) => fmtNum(Number(v), 4)
							},
							{
								key: 'mean_p',
								label: 'MEAN P',
								align: 'right',
								fmt: (v) => fmtNum(Number(v), 3)
							},
							{
								key: 'mean_y',
								label: 'MEAN Y',
								align: 'right',
								fmt: (v) => fmtNum(Number(v), 3)
							},
							{
								key: 'edge_proxy',
								label: 'P−Y',
								align: 'right',
								fmt: (v) => fmtNum(Number(v), 3)
							}
						]}
						rows={calRows}
					/>
				{/if}
			</Panel>
		</div>

		<Panel title="How to refresh research" tag="OPS" accent="none" compact>
			<pre class="pre mono"># pinned calendar (stable cuts while eod_bulk grows)
# research-only: --no-promote so mission latest_flight is not clobbered
python -m aether.cli walkforward --lacie --folds 5 --universe hybrid_sector_mission \
  --max-positions 3 --min-confidence 0.58 --start 2019-01-01 --end 2026-07-10
python -m aether.cli engine-flight --lacie --universe hybrid_sector_mission \
  --max-positions 3 --min-confidence 0.58 --name hybrid_c58_pos3 --no-promote
python -m aether.cli engine-flight --lacie --max-positions 5 --name lacie_best_risk \
  --symbols SPY,QQQ,IWM,SQQQ,SH,AAPL,NVDA
python -m aether.cli walkforward --lacie --universe mega_plus_bench --folds 4 --max-positions 5
python -m aether.cli risk-sweep --lacie --symbols SPY,QQQ,IWM,SQQQ,SH,AAPL,NVDA
python -m aether.cli horizon --lacie --max-positions 5
python -m aether.cli engine-flight --json-dir /Volumes/LaCie/Aether/data/raw/fmp/bonds/ohlcv_eod \
  --symbols AGG,BND,TLT,HYG,LQD --name bonds_core_flight --no-promote
python -m aether.cli status</pre>
		</Panel>
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
	.grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: var(--gap);
	}
	.meta {
		margin: 0 0 8px;
		font-size: 10px;
		color: var(--text-mute);
		letter-spacing: 0.06em;
	}
	.pending {
		color: var(--amber);
		font-size: 11px;
		padding: 12px;
	}
	.pending code {
		color: var(--cyan);
	}
	.pre {
		margin: 0;
		padding: 10px;
		background: #080c14;
		border: 1px solid var(--border);
		font-size: 11px;
		color: var(--cyan);
		overflow: auto;
		line-height: 1.5;
	}
	@media (max-width: 1100px) {
		.hero,
		.grid {
			grid-template-columns: 1fr;
		}
	}
</style>
