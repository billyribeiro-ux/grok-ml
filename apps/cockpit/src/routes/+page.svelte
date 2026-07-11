<script lang="ts">
	import { onMount } from 'svelte';
	import type { PageData } from './$types';
	import Shell from '$lib/components/Shell.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import MetricTile from '$lib/components/MetricTile.svelte';
	import BarMeter from '$lib/components/BarMeter.svelte';
	import SignalFunnel from '$lib/components/SignalFunnel.svelte';
	import RiskGeometry from '$lib/components/RiskGeometry.svelte';
	import UniverseRail from '$lib/components/UniverseRail.svelte';
	import EquityChart from '$lib/components/EquityChart.svelte';
	import OhlcChart from '$lib/components/OhlcChart.svelte';
	import CalibrationChart from '$lib/components/CalibrationChart.svelte';
	import DataTable from '$lib/components/DataTable.svelte';
	import FeatureWeights from '$lib/components/FeatureWeights.svelte';
	import RegimeSpark from '$lib/components/RegimeSpark.svelte';
	import {
		fmtPct,
		fmtNum,
		fmtInt,
		fmtUsd,
		fmtBrier,
		fmtUtcIso,
		signClass
	} from '$lib/format';
	import { resolveFlight } from '$lib/flightBook.svelte';

	let { data }: { data: PageData } = $props();

	const flight = $derived(resolveFlight(data.flight));
	const stats = $derived(flight?.stats ?? {});
	const extra = $derived(flight?.extra ?? {});
	const symbols = $derived(flight?.symbols ?? []);
	const laws = $derived(flight?.laws ?? {});
	const series = $derived(flight?.series);
	const equity = $derived(series?.equity_curve ?? []);
	const fills = $derived(series?.fills ?? []);
	const calBins = $derived(series?.calibration_bins ?? []);
	const ohlc = $derived(series?.ohlc ?? {});
	const sigSummary = $derived(series?.signal_summary ?? {});
	const weights = $derived(series?.feature_weights ?? []);
	const rejSummary = $derived(series?.rejection_summary ?? {});
	const fillByReason = $derived(series?.fill_summary?.by_reason ?? {});
	const regimeDaily = $derived(
		Array.isArray(extra.regime_daily) ? (extra.regime_daily as Record<string, unknown>[]) : []
	);

	let selected = $state<string | null>(null);
	let activePanel = $state<'MISSION' | 'RISK' | 'FUNNEL' | 'CAL' | 'GAPS'>('MISSION');

	const focus = $derived(selected ?? symbols[0] ?? null);
	const focusBars = $derived(focus && ohlc[focus] ? ohlc[focus] : []);
	const retTone = $derived(signClass(stats.total_return));

	const trainFrac = $derived(typeof extra.train_frac === 'number' ? extra.train_frac : null);
	const brier = $derived(
		typeof extra.calibration_brier === 'number' ? extra.calibration_brier : null
	);
	const trainRows = $derived(typeof extra.train_rows === 'number' ? extra.train_rows : null);
	const testRows = $derived(typeof extra.test_rows === 'number' ? extra.test_rows : null);
	const cutDate = $derived(
		typeof extra.cut_date === 'string' ? String(extra.cut_date).slice(0, 10) : '—'
	);

	const standDownRate = $derived.by(() => {
		const s = stats.n_signals;
		const d = stats.n_stand_down;
		if (typeof s !== 'number' || !s || typeof d !== 'number') return null;
		return d / s;
	});
	const fillRate = $derived.by(() => {
		const a = stats.n_actionable_signals;
		const f = stats.n_fills;
		if (typeof a !== 'number' || !a || typeof f !== 'number') return null;
		return f / a;
	});

	const recentFills = $derived(
		[...fills].reverse().slice(0, 40) as Record<string, unknown>[]
	);

	const fkeys = [
		{ k: 'F1', label: 'MISSION', id: 'MISSION' as const },
		{ k: 'F2', label: 'RISK', id: 'RISK' as const },
		{ k: 'F3', label: 'FUNNEL', id: 'FUNNEL' as const },
		{ k: 'F4', label: 'CALIB', id: 'CAL' as const },
		{ k: 'F5', label: 'GAPS', id: 'GAPS' as const }
	];

	onMount(() => {
		function onKey(e: KeyboardEvent) {
			if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)
				return;
			const map: Record<string, typeof activePanel> = {
				F1: 'MISSION',
				F2: 'RISK',
				F3: 'FUNNEL',
				F4: 'CAL',
				F5: 'GAPS'
			};
			if (map[e.key]) {
				e.preventDefault();
				activePanel = map[e.key];
			}
			if (e.key === '1' || e.key === '2' || e.key === '3' || e.key === '4' || e.key === '5') {
				const idx = Number(e.key) - 1;
				if (symbols[idx]) selected = symbols[idx];
			}
		}
		window.addEventListener('keydown', onKey);
		return () => window.removeEventListener('keydown', onKey);
	});

	function interpret(k: string): string {
		const map: Record<string, string> = {
			total_return: 'Compounded paper return over OOS window',
			ann_vol: 'Annualized volatility of equity path',
			sharpe_like: 'Ann. return / ann. vol (not risk-free adj.)',
			max_drawdown: 'Worst peak-to-trough on paper equity',
			n_fills: 'Executed paper fills after risk/policy',
			n_signals: 'Raw scorer emissions (incl. silence)',
			n_stand_down: 'Explicit STAND_DOWN decisions',
			n_actionable_signals: 'Signals that cleared conviction',
			n_rejections: 'Risk / size / cost rejections',
			final_equity_usd: 'Terminal paper equity (USD)'
		};
		return map[k] ?? 'Flight statistic';
	}
</script>

<Shell
	flight={flight}
	env={data.env}
	pathUsed={data.pathUsed}
	loadedAt={data.loadedAt}
	activePanel={activePanel}
	onPanel={(id) => {
		if (id === 'MISSION' || id === 'RISK' || id === 'FUNNEL' || id === 'CAL' || id === 'GAPS')
			activePanel = id;
	}}
	onSymbol={(s) => (selected = s)}
>
	<nav class="fkeys" aria-label="Function keys">
		{#each fkeys as fk (fk.k)}
			<button
				type="button"
				class:active={activePanel === fk.id}
				onclick={() => (activePanel = fk.id)}
			>
				<span class="fk mono">{fk.k}</span>
				<span class="fl">{fk.label}</span>
			</button>
		{/each}
		<div class="fk-hint mono">
			/ COMMAND · 1–5 SYMBOL · F1–F5 · SERIES {series ? 'ON' : 'PENDING'}
		</div>
	</nav>

	<div class="workspace">
		<aside class="left">
			<Panel title="Universe" tag="FLIGHT" accent="amber" compact>
				<UniverseRail
					{symbols}
					selected={focus}
					source={flight?.source ?? '—'}
					onSelect={(s) => (selected = s)}
				/>
			</Panel>
		</aside>

		<section class="center">
			<div class="hero-row">
				<MetricTile
					label="Total Return"
					value={fmtPct(stats.total_return)}
					sub="walk-forward paper"
					tone={retTone}
					large
				/>
				<MetricTile
					label="Final Equity"
					value={fmtUsd(stats.final_equity_usd)}
					sub="USD end of flight"
					tone="pos"
					large
				/>
				<MetricTile
					label="Sharpe-like"
					value={fmtNum(stats.sharpe_like, 3)}
					sub="ann ret / ann vol"
					tone="cyan"
					large
				/>
				<MetricTile
					label="Max Drawdown"
					value={fmtPct(stats.max_drawdown)}
					sub="peak-to-trough"
					tone="neg"
					large
				/>
			</div>

			<Panel title="Paper Equity Curve" tag="REAL SERIES" accent="cyan">
				{#if equity.length}
					<EquityChart points={equity} height={200} />
				{:else}
					<p class="pending mono">
						EQUITY SERIES PENDING — re-run
						<code>python -m aether.cli engine-flight --lacie</code>
					</p>
				{/if}
				{#snippet footer()}
					From backtest equity_cents path · not a fabricated curve
				{/snippet}
			</Panel>

			<div class="chart-split">
				<Panel title="Focus Chart" tag={focus ?? '—'} accent="amber">
					{#key focus}
						<OhlcChart symbol={focus ?? '—'} bars={focusBars} height={220} />
					{/key}
					{#snippet footer()}
						OOS daily bars from flight features · no live quotes
					{/snippet}
				</Panel>
				<div class="main-panels-side">
					{#if activePanel === 'MISSION' || activePanel === 'RISK'}
						<Panel title="Risk Geometry" tag="STATS→RINGS" accent="red" compact>
							{#if flight}
								<RiskGeometry
									maxDrawdown={stats.max_drawdown}
									annVol={stats.ann_vol}
									sharpe={stats.sharpe_like}
									totalReturn={stats.total_return}
								/>
							{:else}
								<p class="pending mono">AWAITING FLIGHT</p>
							{/if}
						</Panel>
					{/if}
					{#if activePanel === 'MISSION' || activePanel === 'FUNNEL'}
						<Panel title="Decision Funnel" tag="POLICY" accent="cyan" compact>
							{#if flight}
								<SignalFunnel
									nSignals={Number(stats.n_signals ?? 0)}
									nStandDown={Number(stats.n_stand_down ?? 0)}
									nActionable={Number(stats.n_actionable_signals ?? 0)}
									nFills={Number(stats.n_fills ?? 0)}
									nRejections={Number(stats.n_rejections ?? 0)}
								/>
							{:else}
								<p class="pending mono">AWAITING FLIGHT</p>
							{/if}
						</Panel>
					{/if}
					{#if activePanel === 'MISSION' || activePanel === 'CAL'}
						<Panel title="Calibration" tag="OOS" accent="violet" compact>
							{#if calBins.length}
								<CalibrationChart bins={calBins} {brier} />
							{:else if flight}
								<div class="cal-grid">
									<MetricTile label="Train frac" value={fmtNum(trainFrac, 2)} />
									<MetricTile label="Cut" value={cutDate} tone="amber" />
									<MetricTile label="Train" value={fmtInt(trainRows)} tone="cyan" />
									<MetricTile label="Test" value={fmtInt(testRows)} tone="cyan" />
									<MetricTile label="Brier" value={fmtBrier(brier)} tone="pos" />
								</div>
								<div class="meters">
									<BarMeter
										label="STAND_DOWN RATE"
										value={standDownRate ?? 0}
										display={fmtPct(standDownRate)}
										tone="amber"
									/>
									<BarMeter
										label="FILL / ACTIONABLE"
										value={fillRate ?? 0}
										display={fmtPct(fillRate)}
										tone="pos"
									/>
								</div>
							{:else}
								<p class="pending mono">AWAITING FLIGHT</p>
							{/if}
						</Panel>
					{/if}
					{#if activePanel === 'GAPS'}
						<Panel title="Honest Gaps" tag="L0" accent="amber" compact>
							<ul class="gaps">
								{#each data.gaps as g (g)}
									<li><span class="bullet">◇</span>{g}</li>
								{/each}
							</ul>
							{#if laws.note}
								<p class="law-note mono">{laws.note}</p>
							{/if}
						</Panel>
					{/if}
				</div>
			</div>

			<div class="bottom-grid">
				<Panel title="Recent Fills" tag={`${fills.length} ROWS`} accent="none" compact>
					<DataTable
						maxHeight="200px"
						empty="NO FILLS IN SERIES — re-run flight"
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
							{ key: 'reason', label: 'REASON' }
						]}
						rows={recentFills}
					/>
				</Panel>
				<Panel title="Signal Mix" tag="SUMMARY" accent="violet" compact>
					{#if sigSummary.by_mode}
						<ul class="mix mono">
							{#each Object.entries(sigSummary.by_mode) as [k, v] (k)}
								<li>
									<span>{k}</span>
									<span class="amber">{fmtInt(v)}</span>
								</li>
							{/each}
						</ul>
						{#if sigSummary.by_symbol}
							<ul class="mix mono">
								{#each Object.entries(sigSummary.by_symbol) as [k, v] (k)}
									<li>
										<span>{k}</span>
										<span class="cyan">{fmtInt(v)}</span>
									</li>
								{/each}
							</ul>
						{/if}
					{:else}
						<p class="pending mono">NO SIGNAL SUMMARY YET</p>
					{/if}
					{#if Object.keys(rejSummary).length}
						<h3 class="subh mono">REJECTIONS</h3>
						<ul class="mix mono">
							{#each Object.entries(rejSummary) as [k, v] (k)}
								<li>
									<span>{k}</span>
									<span class="neg">{fmtInt(v)}</span>
								</li>
							{/each}
						</ul>
					{/if}
					{#if Object.keys(fillByReason).length}
						<h3 class="subh mono">FILL REASONS</h3>
						<ul class="mix mono">
							{#each Object.entries(fillByReason) as [k, v] (k)}
								<li>
									<span>{k}</span>
									<span class="cyan">{fmtInt(v)}</span>
								</li>
							{/each}
						</ul>
					{/if}
				</Panel>
			</div>

			<div class="bottom-grid">
				<Panel title="Feature Weights" tag="LOGISTIC" accent="violet" compact>
					<FeatureWeights {weights} />
					{#snippet footer()}
						Walk-forward logistic coefficients · not causal claims
					{/snippet}
				</Panel>
				<Panel
					title="Regime Strip (OOS median)"
					tag={`${regimeDaily.length} DAYS`}
					accent="cyan"
					compact
				>
					{#if regimeDaily.length}
						<RegimeSpark
							points={regimeDaily.map((r) => ({
								date: String(r.date ?? ''),
								trend_energy: r.trend_energy != null ? Number(r.trend_energy) : undefined,
								breadth_integrity:
									r.breadth_integrity != null ? Number(r.breadth_integrity) : undefined,
								vol_regime: r.vol_regime != null ? Number(r.vol_regime) : undefined,
								uncertainty: r.uncertainty != null ? Number(r.uncertainty) : undefined
							}))}
							height={72}
						/>
						<table class="score">
							<thead>
								<tr>
									<th>DATE</th>
									<th>TREND</th>
									<th>BREADTH</th>
									<th>VOL</th>
									<th>UNC</th>
								</tr>
							</thead>
							<tbody>
								{#each regimeDaily.slice(-8) as r, i (i)}
									<tr>
										<td class="mono key">{String(r.date ?? '—')}</td>
										<td class="mono val">{fmtNum(Number(r.trend_energy), 3)}</td>
										<td class="mono val">{fmtNum(Number(r.breadth_integrity), 3)}</td>
										<td class="mono val">{fmtNum(Number(r.vol_regime), 3)}</td>
										<td class="mono val">{fmtNum(Number(r.uncertainty), 3)}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					{:else}
						<p class="pending mono">NO REGIME DAILY IN EXTRA — re-run flight</p>
					{/if}
				</Panel>
			</div>

			<Panel title="Scoreboard" tag="RAW STATS" accent="none" compact>
				{#if flight && Object.keys(stats).length}
					<table class="score">
						<thead>
							<tr>
								<th>FIELD</th>
								<th>VALUE</th>
								<th>INTERPRETATION</th>
							</tr>
						</thead>
						<tbody>
							{#each Object.entries(stats) as [k, v] (k)}
								<tr>
									<td class="mono key">{k}</td>
									<td class="mono val">
										{#if typeof v === 'number'}
											{#if k.includes('return') || k.includes('drawdown') || k.includes('vol')}
												<span class={signClass(v)}>{fmtPct(v)}</span>
											{:else if k.includes('equity')}
												{fmtUsd(v)}
											{:else if Number.isInteger(v)}
												{fmtInt(v)}
											{:else}
												{fmtNum(v, 4)}
											{/if}
										{:else}
											{v ?? '—'}
										{/if}
									</td>
									<td class="interp">{interpret(k)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				{:else}
					<p class="pending mono">NO STATS</p>
				{/if}
			</Panel>
		</section>

		<aside class="right">
			<Panel title="Flight Card" tag="META" accent="cyan" compact>
				{#if flight}
					<dl class="kv">
						<div>
							<dt>NAME</dt>
							<dd class="mono">{flight.name}</dd>
						</div>
						<div>
							<dt>SOURCE</dt>
							<dd class="mono">{flight.source}</dd>
						</div>
						<div>
							<dt>WRITTEN</dt>
							<dd class="mono">{fmtUtcIso(flight.written_at)}</dd>
						</div>
						<div>
							<dt>FOCUS</dt>
							<dd class="mono amber">{focus ?? '—'}</dd>
						</div>
						<div>
							<dt>SERIES</dt>
							<dd class="mono">
								eq={equity.length} fills={fills.length} ohlc={Object.keys(ohlc).length}
							</dd>
						</div>
						<div>
							<dt>CUT</dt>
							<dd class="mono">{cutDate}</dd>
						</div>
					</dl>
				{:else}
					<p class="pending mono">NO FLIGHT</p>
				{/if}
			</Panel>
			<Panel title="Laws" tag="CONSTITUTION" accent="green" compact>
				<ul class="laws">
					<li>
						<span class="l">L0</span><span>Truth</span>
						<span class="s {laws.L0_truth ? 'pos' : 'neg'}">{laws.L0_truth ? 'ON' : '—'}</span>
					</li>
					<li>
						<span class="l">L1</span><span>STAND_DOWN = success</span>
						<span class="s pos">ON</span>
					</li>
					<li>
						<span class="l">L2</span><span>Human kill-switch</span>
						<span class="s amber">ARMED</span>
					</li>
					<li>
						<span class="l">L3</span><span>Money cents/i64</span>
						<span class="s pos">ON</span>
					</li>
					<li>
						<span class="l">L4</span><span>No live routing</span>
						<span class="s cyan">PAPER</span>
					</li>
				</ul>
			</Panel>
			<Panel title="Ops" tag="STATUS" accent="none" compact>
				<div class="ops mono">
					<div class="ops-row"><span>ENV</span><span class="amber">{data.env}</span></div>
					<div class="ops-row">
						<span>TELEMETRY</span>
						<span class={flight ? 'pos' : 'neg'}>{flight ? 'LINKED' : 'MISSING'}</span>
					</div>
					<div class="ops-row">
						<span>SERIES</span>
						<span class={series ? 'pos' : 'amber'}>{series ? 'RICH' : 'STATS-ONLY'}</span>
					</div>
					<div class="ops-row">
						<span>API</span>
						<span class="cyan">/api/flight</span>
					</div>
				</div>
			</Panel>
		</aside>
	</div>
</Shell>

<style>
	.fkeys {
		display: flex;
		align-items: stretch;
		background: #060a11;
		border-bottom: 1px solid var(--border);
		height: var(--fkey-h);
	}
	.fkeys button {
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 0 12px;
		background: transparent;
		border: none;
		border-right: 1px solid var(--border);
		color: var(--text-dim);
		cursor: pointer;
		font: inherit;
	}
	.fkeys button:hover {
		background: var(--bg-hover);
		color: var(--text);
	}
	.fkeys button.active {
		background: rgba(255, 176, 32, 0.1);
		color: var(--amber);
		box-shadow: inset 0 -2px 0 var(--amber);
	}
	.fk {
		font-size: 10px;
		font-weight: 700;
		color: var(--amber);
	}
	.fl {
		font-family: var(--font-mono);
		font-size: 10px;
		letter-spacing: 0.1em;
	}
	.fk-hint {
		margin-left: auto;
		display: flex;
		align-items: center;
		padding: 0 12px;
		font-size: 9px;
		color: var(--text-faint);
		letter-spacing: 0.08em;
	}
	.workspace {
		display: grid;
		grid-template-columns: 190px 1fr 240px;
		gap: var(--gap);
		padding: var(--gap);
		min-height: calc(100vh - var(--header-h) - var(--ticker-h) - var(--fkey-h) - var(--status-h) - 8px);
	}
	.left,
	.right,
	.center {
		min-height: 0;
		display: flex;
		flex-direction: column;
		gap: var(--gap);
	}
	.center {
		overflow: auto;
	}
	.right {
		overflow: auto;
	}
	.left :global(.panel) {
		flex: 1;
		min-height: 280px;
	}
	.hero-row {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: var(--gap);
	}
	.chart-split {
		display: grid;
		grid-template-columns: 1.3fr 1fr;
		gap: var(--gap);
	}
	.main-panels-side {
		display: flex;
		flex-direction: column;
		gap: var(--gap);
		min-height: 0;
	}
	.bottom-grid {
		display: grid;
		grid-template-columns: 1.4fr 1fr;
		gap: var(--gap);
	}
	.cal-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 6px;
		margin-bottom: 8px;
	}
	.meters {
		margin-top: 4px;
	}
	.score {
		width: 100%;
		border-collapse: collapse;
		font-size: 11px;
	}
	.score th {
		text-align: left;
		font-family: var(--font-mono);
		font-size: 9px;
		letter-spacing: 0.12em;
		color: var(--text-mute);
		padding: 4px 8px 6px 0;
		border-bottom: 1px solid var(--border);
	}
	.score td {
		padding: 5px 8px 5px 0;
		border-bottom: 1px solid rgba(255, 255, 255, 0.03);
	}
	.score .key {
		color: var(--text-dim);
	}
	.score .val {
		font-weight: 600;
	}
	.score .interp {
		color: var(--text-mute);
		font-size: 10px;
	}
	.kv {
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.kv dt {
		font-family: var(--font-mono);
		font-size: 9px;
		letter-spacing: 0.12em;
		color: var(--text-mute);
	}
	.kv dd {
		margin: 0;
		font-size: 11px;
		word-break: break-all;
	}
	.laws {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	.laws li {
		display: grid;
		grid-template-columns: 28px 1fr auto;
		gap: 6px;
		font-size: 10px;
		color: var(--text-dim);
	}
	.laws .l {
		font-family: var(--font-mono);
		font-weight: 700;
		color: var(--amber);
	}
	.laws .s {
		font-family: var(--font-mono);
		font-size: 9px;
		font-weight: 700;
	}
	.ops {
		display: flex;
		flex-direction: column;
		gap: 6px;
		font-size: 10px;
	}
	.ops-row {
		display: flex;
		justify-content: space-between;
	}
	.gaps {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.gaps li {
		display: flex;
		gap: 8px;
		padding: 5px 0;
		border-bottom: 1px solid rgba(255, 255, 255, 0.04);
		font-size: 11px;
		color: var(--text-dim);
	}
	.bullet {
		color: var(--amber);
	}
	.law-note {
		margin: 10px 0 0;
		padding: 8px;
		border: 1px solid var(--border-amber);
		background: rgba(255, 176, 32, 0.06);
		color: var(--amber);
		font-size: 10px;
	}
	.mix {
		list-style: none;
		margin: 0 0 10px;
		padding: 0;
	}
	.mix li {
		display: flex;
		justify-content: space-between;
		padding: 3px 0;
		border-bottom: 1px solid rgba(255, 255, 255, 0.03);
		font-size: 11px;
		color: var(--text-dim);
	}
	.subh {
		margin: 10px 0 4px;
		font-size: 9px;
		letter-spacing: 0.12em;
		color: var(--text-mute);
	}
	.pending {
		color: var(--amber);
		font-size: 11px;
		letter-spacing: 0.06em;
		padding: 12px 4px;
	}
	.pending code {
		color: var(--cyan);
	}
	@media (max-width: 1200px) {
		.workspace {
			grid-template-columns: 160px 1fr;
		}
		.right {
			display: none;
		}
		.hero-row {
			grid-template-columns: repeat(2, 1fr);
		}
		.chart-split,
		.bottom-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
