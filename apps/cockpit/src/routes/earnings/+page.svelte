<script lang="ts">
	import type { PageData } from './$types';
	import Shell from '$lib/components/Shell.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import MetricTile from '$lib/components/MetricTile.svelte';
	import { fmtInt, fmtNum, fmtPct } from '$lib/format';

	let { data }: { data: PageData } = $props();

	const flight = $derived(data.flight);
	const summaries = $derived(data.earnings?.summaries ?? {});
	const panels = $derived(data.earnings?.panels ?? {});
	const specialists = $derived(data.earnings?.specialists ?? {});
	const mtfResearch = $derived(data.earnings?.mtfResearch ?? {});
	const mtf = $derived(data.mtf ?? {});
	const sp = $derived((summaries.sp500 ?? null) as Record<string, unknown> | null);
	const iwm = $derived((summaries.iwm ?? null) as Record<string, unknown> | null);
	const spSpec = $derived((specialists.sp500 ?? null) as Record<string, unknown> | null);

	function meanOf(s: Record<string, unknown> | null, key: string): number | null {
		if (!s) return null;
		const block = s[key] as { mean?: number } | undefined;
		return block?.mean ?? null;
	}

	const panelRows = $derived(
		Object.entries(panels).map(([name, v]) => ({
			name,
			exists: Boolean(v.exists),
			path: String(v.path ?? '')
		}))
	);

	const mtfRows = $derived(
		Object.entries(mtf).map(([u, ivs]) => ({
			universe: u,
			...(ivs as Record<string, number>)
		}))
	);
</script>

<Shell flight={flight} env={data.env} pathUsed={data.pathUsed} loadedAt={data.loadedAt}>
	<div class="page">
		<div class="hero">
			<MetricTile label="Window" value="2018→2026-07-10" tone="cyan" large />
			<MetricTile
				label="SP500 events"
				value={fmtInt(sp?.n_events as number)}
				sub={sp ? `${fmtInt(sp.n_symbols as number)} symbols` : 'pending build'}
				tone="pos"
				large
			/>
			<MetricTile
				label="Beat post 1d"
				value={fmtPct(sp?.beat_post_ret_1d_mean as number)}
				sub={sp ? `n=${fmtInt(sp.beat_n as number)}` : '—'}
				tone="pos"
				large
			/>
			<MetricTile
				label="Specialist long OOS"
				value={fmtPct(spSpec?.long_only_mean_post_1d as number)}
				sub={spSpec ? `acc ${fmtNum(spSpec.accuracy as number, 3)}` : 'run earn-ml'}
				tone="pos"
				large
			/>
		</div>

		<div class="grid">
			<Panel title="Earnings Calendar Panels" tag="LA CIE ARCHIVE" accent="amber">
				<p class="note mono">
					Hard pin {data.window}. BMO/AMC times from daily calendar (not invented).
				</p>
				<table class="tbl">
					<thead>
						<tr>
							<th>PANEL</th>
							<th>OK</th>
							<th>PATH</th>
						</tr>
					</thead>
					<tbody>
						{#each panelRows as r (r.name)}
							<tr>
								<td class="mono">{r.name}</td>
								<td class={r.exists ? 'pos' : 'neg'}>{r.exists ? 'YES' : 'NO'}</td>
								<td class="mono path">{r.path}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</Panel>

			<Panel title="Event Study Means" tag="PRE / POST" accent="cyan">
				{#if !sp && !iwm}
					<p class="pending mono">
						Event tables pending — run
						<code>python scripts/build_earnings_event_tables.py</code>
					</p>
				{:else}
					<table class="tbl">
						<thead>
							<tr>
								<th>UNIV</th>
								<th class="r">N</th>
								<th class="r">PRE 5D</th>
								<th class="r">GAP</th>
								<th class="r">POST 1D</th>
								<th class="r">POST 5D</th>
								<th class="r">BEAT 1D</th>
								<th class="r">MISS 1D</th>
							</tr>
						</thead>
						<tbody>
							{#each Object.entries(summaries) as [u, s] (u)}
								{@const row = s as Record<string, unknown>}
								<tr>
									<td class="mono">{u}</td>
									<td class="r mono">{fmtInt(row.n_events as number)}</td>
									<td class="r mono">{fmtPct(meanOf(row, 'pre_ret_5d'))}</td>
									<td class="r mono">{fmtPct(meanOf(row, 'gap_ret'))}</td>
									<td class="r mono">{fmtPct(meanOf(row, 'post_ret_1d'))}</td>
									<td class="r mono">{fmtPct(meanOf(row, 'post_ret_5d'))}</td>
									<td class="r mono pos">{fmtPct(row.beat_post_ret_1d_mean as number)}</td>
									<td class="r mono neg">{fmtPct(row.miss_post_ret_1d_mean as number)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				{/if}
			</Panel>

			<Panel title="Earnings Specialist (pre-event)" tag="OOS TIME-CUT" accent="pos">
				{#if !Object.keys(specialists).length}
					<p class="pending mono">
						Run <code>python -m aether.cli earnings-specialist --universe sp500</code>
					</p>
				{:else}
					<table class="tbl">
						<thead>
							<tr>
								<th>UNIV</th>
								<th class="r">N TEST</th>
								<th class="r">ACC</th>
								<th class="r">BASE</th>
								<th class="r">LIFT</th>
								<th class="r">LONG µ1d</th>
								<th class="r">SHORT µ1d</th>
								<th>CUT</th>
							</tr>
						</thead>
						<tbody>
							{#each Object.entries(specialists) as [u, s] (u)}
								{@const row = s as Record<string, unknown>}
								<tr>
									<td class="mono">{u}</td>
									<td class="r mono">{fmtInt(row.n_test as number)}</td>
									<td class="r mono">{fmtNum(row.accuracy as number, 3)}</td>
									<td class="r mono">{fmtNum(row.base_rate as number, 3)}</td>
									<td class="r mono">{fmtNum(row.lift as number, 3)}</td>
									<td class="r mono pos">{fmtPct(row.long_only_mean_post_1d as number)}</td>
									<td class="r mono neg">{fmtPct(row.short_only_mean_post_1d as number)}</td>
									<td class="mono">{String(row.cut_date ?? '—')}</td>
								</tr>
							{/each}
						</tbody>
					</table>
					<p class="note mono">
						Pre-event features only (no epsActual). Classification ~base-rate is honest; ranking
						edge shows in long/short mean post returns when confidence filters fire.
					</p>
				{/if}
			</Panel>

			<Panel title="SP500 Multi-TF Research" tag="LOCAL CHARTS" accent="cyan">
				{#if !Object.keys(mtfResearch).length}
					<p class="pending mono">
						Run <code>python -m aether.cli mtf-research --interval 15min</code>
					</p>
				{:else}
					<table class="tbl">
						<thead>
							<tr>
								<th>RUN</th>
								<th class="r">SYMS</th>
								<th class="r">BARS</th>
								<th class="r">ACC</th>
								<th class="r">LIFT</th>
								<th class="r">LONG µ</th>
							</tr>
						</thead>
						<tbody>
							{#each Object.entries(mtfResearch) as [name, s] (name)}
								{@const row = s as Record<string, unknown>}
								<tr>
									<td class="mono">{name}</td>
									<td class="r mono">{fmtInt(row.n_symbols as number)}</td>
									<td class="r mono">{fmtInt(row.n_bars as number)}</td>
									<td class="r mono">{fmtNum(row.accuracy as number, 3)}</td>
									<td class="r mono">{fmtNum(row.lift as number, 3)}</td>
									<td class="r mono">{fmtPct(row.mean_fwd_when_long as number)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				{/if}
			</Panel>

			<Panel title="Multi-TF Price Archive" tag="TRANSFER IN FLIGHT" accent="violet">
				<table class="tbl">
					<thead>
						<tr>
							<th>UNIV</th>
							<th class="r">EOD</th>
							<th class="r">1H</th>
							<th class="r">15M</th>
							<th class="r">5M</th>
							<th class="r">1M</th>
						</tr>
					</thead>
					<tbody>
						{#each mtfRows as r (r.universe)}
							<tr>
								<td class="mono">{r.universe}</td>
								<td class="r mono">{fmtInt(r.eod)}</td>
								<td class="r mono">{fmtInt(r['1hour'])}</td>
								<td class="r mono">{fmtInt(r['15min'])}</td>
								<td class="r mono">{fmtInt(r['5min'])}</td>
								<td class="r mono">{fmtInt(r['1min'])}</td>
							</tr>
						{/each}
					</tbody>
				</table>
				<p class="note mono">
					Counts are file presence on LaCie — empty markers count as files; ML should filter
					empty.
				</p>
			</Panel>

			<Panel title="Mission (2018 pin)" tag="PROMOTED" accent="pos">
				{#if flight?.stats}
					<div class="mission">
						<div class="mono name">{flight.name}</div>
						<div class="row">
							<span>Return</span><span class="mono pos">{fmtPct(flight.stats.total_return)}</span>
						</div>
						<div class="row">
							<span>Sharpe~</span><span class="mono">{fmtNum(flight.stats.sharpe_like, 3)}</span>
						</div>
						<div class="row">
							<span>Max DD</span><span class="mono neg">{fmtPct(flight.stats.max_drawdown)}</span>
						</div>
						<div class="row">
							<span>Fills</span><span class="mono">{fmtInt(flight.stats.n_fills)}</span>
						</div>
					</div>
				{:else}
					<p class="pending mono">No mission telemetry</p>
				{/if}
			</Panel>
		</div>
	</div>
</Shell>

<style>
	.page {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		padding: 0.5rem 0 2rem;
	}
	.hero {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 0.75rem;
	}
	.grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.75rem;
	}
	.tbl {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.78rem;
	}
	.tbl th,
	.tbl td {
		padding: 0.35rem 0.4rem;
		border-bottom: 1px solid color-mix(in srgb, var(--border, #333) 80%, transparent);
		text-align: left;
	}
	.tbl th {
		opacity: 0.7;
		font-weight: 600;
		letter-spacing: 0.04em;
	}
	.r {
		text-align: right;
	}
	.mono {
		font-family: var(--font-mono, ui-monospace, monospace);
	}
	.path {
		font-size: 0.68rem;
		opacity: 0.75;
		word-break: break-all;
	}
	.pos {
		color: var(--pos, #3dffa8);
	}
	.neg {
		color: var(--neg, #ff6b6b);
	}
	.note,
	.pending {
		font-size: 0.75rem;
		opacity: 0.8;
		margin: 0 0 0.6rem;
	}
	.mission {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}
	.mission .name {
		font-size: 0.85rem;
		margin-bottom: 0.3rem;
	}
	.mission .row {
		display: flex;
		justify-content: space-between;
		font-size: 0.8rem;
	}
	@media (max-width: 1100px) {
		.hero,
		.grid {
			grid-template-columns: 1fr;
		}
	}
</style>
