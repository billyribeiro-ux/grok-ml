<script lang="ts">
	import type { PageData } from './$types';
	import Shell from '$lib/components/Shell.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import MetricTile from '$lib/components/MetricTile.svelte';
	import { fmtInt, fmtNum, fmtUsd, fmtPct } from '$lib/format';

	let { data }: { data: PageData } = $props();
	const status = $derived(data.status as Record<string, unknown> | null);
	const archives = $derived(
		(status?.archives as Record<string, Record<string, unknown>> | undefined) ?? {}
	);
	const archiveRows = $derived(
		Object.entries(archives).map(([name, v]) => ({
			name,
			exists: Boolean(v.exists),
			files: Number(v.files_approx ?? 0),
			dirs: Number(v.subdirs ?? 0),
			mb: Number(v.mb ?? 0)
		}))
	);
	const logs = $derived(
		(status?.download_logs as Record<string, { tail?: string[]; lines?: number }> | undefined) ??
			{}
	);
	const tel = $derived((status?.telemetry as Record<string, unknown> | undefined) ?? {});
	const flight = $derived(data.flight);
	const stats = $derived(flight?.stats ?? {});
	const mtf = $derived(data.mtf ?? {});
	const ready = $derived(data.ready as Record<string, unknown> | null);
	const pre8 = $derived(data.pre8 ?? {});
	const canRun = $derived(
		((ready?.can_run_now as string[] | undefined) ?? []).join(', ') || '—'
	);
	const waiting = $derived(
		((ready?.still_waiting as string[] | undefined) ?? []).join(', ') || '—'
	);
	const mtfRows = $derived(
		Object.entries(mtf).map(([u, v]) => ({
			universe: u,
			...(v as Record<string, number>)
		}))
	);
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
				label="LaCie"
				value={status?.lacie_mounted ? 'MOUNTED' : 'MISSING'}
				tone={status?.lacie_mounted ? 'pos' : 'neg'}
				large
			/>
			<MetricTile
				label="EOD bulk files"
				value={fmtInt(archives.eod_bulk?.files_approx as number)}
				sub={`${fmtNum(archives.eod_bulk?.mb as number, 0)} MB`}
				tone="cyan"
				large
			/>
			<MetricTile
				label="Latest flight equity"
				value={fmtUsd(stats.final_equity_usd)}
				tone="pos"
				large
			/>
			<MetricTile
				label="Flight return"
				value={fmtPct(stats.total_return)}
				tone={(stats.total_return as number) >= 0 ? 'pos' : 'neg'}
				large
			/>
		</div>

		<div class="grid">
			<Panel title="Ready vs Waiting" tag="MAIN PROMPT" accent="pos">
				<div class="row2">
					<div>
						<div class="lbl">CAN RUN NOW</div>
						<div class="mono ok">{canRun}</div>
					</div>
					<div>
						<div class="lbl">STILL WAITING</div>
						<div class="mono warn">{waiting}</div>
					</div>
				</div>
			</Panel>

			<Panel title="Multi-TF Fill (live)" tag="IWM + NASDAQ GRIND" accent="cyan">
				<table class="tbl">
					<thead>
						<tr>
							<th>UNIV</th>
							<th class="r">EOD</th>
							<th class="r">1H</th>
							<th class="r">15M</th>
							<th class="r">5M</th>
							<th class="r">1M</th>
							<th class="r">TGT</th>
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
								<td class="r mono dim">{fmtInt(r.target)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</Panel>

			<Panel title="Pre8 Paper Backtest" tag="BUY RUMOR" accent="violet">
				{#if !Object.keys(pre8).length || !Object.values(pre8).some(Boolean)}
					<p class="pending mono">Run <code>python -m aether.cli pre8-backtest</code></p>
				{:else}
					<table class="tbl">
						<thead>
							<tr>
								<th>UNIV</th>
								<th class="r">N LONG</th>
								<th class="r">MEAN</th>
								<th class="r">HIT</th>
								<th class="r">CUM*</th>
								<th class="r">MAX DD</th>
							</tr>
						</thead>
						<tbody>
							{#each Object.entries(pre8) as [u, s] (u)}
								{#if s}
									{@const row = s as Record<string, unknown>}
									<tr>
										<td class="mono">{u}</td>
										<td class="r mono">{fmtInt(row.n_long as number)}</td>
										<td class="r mono">{fmtPct(row.mean_long as number)}</td>
										<td class="r mono">{fmtPct(row.hit_rate_long as number)}</td>
										<td class="r mono">{fmtPct(row.cum_long_only as number)}</td>
										<td class="r mono">{fmtPct(row.max_dd_long_only as number)}</td>
									</tr>
								{/if}
							{/each}
						</tbody>
					</table>
					<p class="pending mono">*Sequential event compound (not concurrent book).</p>
				{/if}
			</Panel>

			<Panel title="Archive Inventory" tag="LIVE WHILE DOWNLOADS RUN" accent="amber">
				{#if !archiveRows.length}
					<p class="pending mono">
						No status snapshot — run
						<code>python -m aether.cli status</code>
					</p>
				{:else}
					<table class="tbl">
						<thead>
							<tr>
								<th>ARCHIVE</th>
								<th>OK</th>
								<th class="r">FILES≈</th>
								<th class="r">DIRS</th>
								<th class="r">MB</th>
							</tr>
						</thead>
						<tbody>
							{#each archiveRows as r (r.name)}
								<tr>
									<td class="mono">{r.name}</td>
									<td class={r.exists ? 'pos' : 'neg'}>{r.exists ? 'YES' : 'NO'}</td>
									<td class="r mono">{fmtInt(r.files)}</td>
									<td class="r mono">{fmtInt(r.dirs)}</td>
									<td class="r mono">{fmtNum(r.mb, 1)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				{/if}
			</Panel>

			<Panel title="Download Log Tails" tag="HONEST PROGRESS" accent="cyan">
				{#each Object.entries(logs) as [name, info] (name)}
					{#if name.includes('bandwidth') || name.includes('nasdaq') || name.includes('session_b') || name.includes('monitor')}
						<div class="logblk">
							<div class="logname mono">{name} · {info.lines ?? 0} lines</div>
							<pre class="tail mono">{(info.tail ?? []).join('\n') || '—'}</pre>
						</div>
					{/if}
				{:else}
					<p class="pending mono">No log tails in status snapshot</p>
				{/each}
			</Panel>

			<Panel title="Flight History Files" tag={String(data.flights.length)} accent="violet">
				<table class="tbl">
					<thead>
						<tr>
							<th>FILE</th>
							<th class="r">MB</th>
							<th>MTIME</th>
						</tr>
					</thead>
					<tbody>
						{#each data.flights as f (f.path)}
							<tr>
								<td class="mono">{f.name}</td>
								<td class="r mono">{(f.bytes / 1e6).toFixed(2)}</td>
								<td class="mono dim">{f.mtime}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</Panel>

			<Panel title="Latest Telemetry Meta" tag="STATUS JSON" accent="green">
				<pre class="pre mono">{JSON.stringify(tel, null, 2)}</pre>
			</Panel>

			<Panel title="Research Index" tag="ARTIFACTS" accent="violet">
				{#if data.researchIndex}
					<pre class="pre mono">{JSON.stringify(data.researchIndex, null, 2)}</pre>
				{:else}
					<p class="pending mono">No research/index.json yet</p>
				{/if}
			</Panel>
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
	.grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: var(--gap);
	}
	.tbl {
		width: 100%;
		border-collapse: collapse;
		font-size: 11px;
	}
	.tbl th {
		text-align: left;
		font-family: var(--font-mono);
		font-size: 9px;
		letter-spacing: 0.1em;
		color: var(--text-mute);
		padding: 4px 6px;
		border-bottom: 1px solid var(--border);
	}
	.tbl td {
		padding: 4px 6px;
		border-bottom: 1px solid rgba(255, 255, 255, 0.03);
		color: var(--text-dim);
	}
	.r {
		text-align: right;
	}
	.dim {
		color: var(--text-faint);
		font-size: 10px;
	}
	.row2 {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 12px;
	}
	.lbl {
		font-size: 9px;
		letter-spacing: 0.1em;
		color: var(--text-mute);
		margin-bottom: 4px;
	}
	.ok {
		color: var(--pos, #3dffa8);
		font-size: 11px;
		line-height: 1.4;
	}
	.warn {
		color: var(--amber, #ffb020);
		font-size: 11px;
		line-height: 1.4;
	}
	.pending {
		font-size: 11px;
		opacity: 0.8;
	}
	.logblk {
		margin-bottom: 10px;
	}
	.logname {
		font-size: 10px;
		color: var(--amber);
		margin-bottom: 4px;
		letter-spacing: 0.06em;
	}
	.tail {
		margin: 0;
		padding: 8px;
		background: #080c14;
		border: 1px solid var(--border);
		font-size: 10px;
		color: var(--text-dim);
		white-space: pre-wrap;
		max-height: 90px;
		overflow: auto;
	}
	.pre {
		margin: 0;
		padding: 8px;
		background: #080c14;
		border: 1px solid var(--border);
		font-size: 10px;
		color: var(--cyan);
		max-height: 320px;
		overflow: auto;
	}
	.pending {
		color: var(--amber);
		font-size: 11px;
	}
	.pending code {
		color: var(--cyan);
	}
	@media (max-width: 1000px) {
		.hero,
		.grid {
			grid-template-columns: 1fr;
		}
	}
</style>
