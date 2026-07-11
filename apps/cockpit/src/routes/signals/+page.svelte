<script lang="ts">
	import type { PageData } from './$types';
	import Shell from '$lib/components/Shell.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import MetricTile from '$lib/components/MetricTile.svelte';
	import DataTable from '$lib/components/DataTable.svelte';
	import { fmtInt, fmtNum, fmtPct } from '$lib/format';

	let { data }: { data: PageData } = $props();
	const flight = $derived(data.flight);
	const series = $derived(flight?.series);
	const signals = $derived(series?.signals ?? []);
	const summary = $derived(series?.signal_summary ?? {});
	const rejections = $derived(series?.rejections ?? []);
	const stats = $derived(flight?.stats ?? {});

	let modeFilter = $state('all');
	let symFilter = $state('all');
	let minConf = $state(0);

	const modes = $derived(
		Array.from(new Set(signals.map((s) => s.mode))).sort()
	);
	const syms = $derived(
		Array.from(new Set(signals.map((s) => s.symbol))).sort()
	);

	const filtered = $derived(
		signals.filter((s) => {
			if (modeFilter !== 'all' && s.mode !== modeFilter) return false;
			if (symFilter !== 'all' && s.symbol !== symFilter) return false;
			if (s.confidence < minConf) return false;
			return true;
		})
	);

	const rows = $derived(
		[...filtered].reverse().map((s) => ({ ...s })) as Record<string, unknown>[]
	);
	const rejRows = $derived(
		[...rejections].reverse().map((r) => ({ ...r })) as Record<string, unknown>[]
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
				label="Signals (payload)"
				value={fmtInt(signals.length)}
				sub={summary.truncated ? `of ${summary.n_total} total` : 'full blotter'}
				tone="cyan"
				large
			/>
			<MetricTile
				label="Actionable (stats)"
				value={fmtInt(stats.n_actionable_signals)}
				tone="pos"
				large
			/>
			<MetricTile
				label="STAND_DOWN"
				value={fmtInt(stats.n_stand_down)}
				tone="amber"
				large
			/>
			<MetricTile
				label="Rejections"
				value={fmtInt(stats.n_rejections)}
				tone="neg"
				large
			/>
		</div>

		<div class="filters mono">
			<label>
				MODE
				<select bind:value={modeFilter}>
					<option value="all">all</option>
					{#each modes as m (m)}
						<option value={m}>{m}</option>
					{/each}
				</select>
			</label>
			<label>
				SYMBOL
				<select bind:value={symFilter}>
					<option value="all">all</option>
					{#each syms as s (s)}
						<option value={s}>{s}</option>
					{/each}
				</select>
			</label>
			<label>
				MIN CONF
				<input type="range" min="0" max="1" step="0.05" bind:value={minConf} />
				<span class="v">{fmtNum(minConf, 2)}</span>
			</label>
			<span class="count">SHOWING {filtered.length}</span>
		</div>

		<div class="grid">
			<Panel title="Signal Blotter" tag="TELEMETRY" accent="cyan">
				<DataTable
					maxHeight="480px"
					empty="NO SIGNALS IN SERIES — re-run engine-flight --lacie"
					columns={[
						{ key: 'date', label: 'DATE' },
						{ key: 'symbol', label: 'SYM' },
						{
							key: 'side',
							label: 'SIDE',
							tone: (r) =>
								r.side === 'long' ? 'pos' : r.side === 'short' ? 'neg' : 'neu'
						},
						{ key: 'mode', label: 'MODE' },
						{
							key: 'confidence',
							label: 'CONF',
							align: 'right',
							fmt: (v) => fmtNum(Number(v), 3)
						},
						{
							key: 'expected_edge',
							label: 'EDGE',
							align: 'right',
							fmt: (v) => fmtPct(Number(v))
						},
						{
							key: 'stop_pct',
							label: 'STOP',
							align: 'right',
							fmt: (v) => fmtPct(Number(v))
						},
						{
							key: 'target_pct',
							label: 'TGT',
							align: 'right',
							fmt: (v) => fmtPct(Number(v))
						},
						{ key: 'reason', label: 'REASON' }
					]}
					{rows}
				/>
			</Panel>

			<div class="side">
				<Panel title="By Mode" tag="MIX" accent="violet" compact>
					<ul class="mix mono">
						{#each Object.entries(summary.by_mode ?? {}) as [k, v] (k)}
							<li>
								<span>{k}</span><span class="amber">{fmtInt(v)}</span>
							</li>
						{/each}
						{#if !summary.by_mode}
							<li class="empty">—</li>
						{/if}
					</ul>
				</Panel>
				<Panel title="By Symbol" tag="MIX" accent="amber" compact>
					<ul class="mix mono">
						{#each Object.entries(summary.by_symbol ?? {}) as [k, v] (k)}
							<li>
								<span>{k}</span><span class="cyan">{fmtInt(v)}</span>
							</li>
						{/each}
					</ul>
				</Panel>
				<Panel title="Risk Rejections" tag={String(rejections.length)} accent="red" compact>
					<DataTable
						maxHeight="200px"
						empty="NO REJECTIONS"
						columns={[
							{ key: 'date', label: 'DATE' },
							{ key: 'symbol', label: 'SYM' },
							{ key: 'reason', label: 'REASON' }
						]}
						rows={rejRows}
					/>
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
	.filters {
		display: flex;
		flex-wrap: wrap;
		gap: 16px;
		align-items: center;
		padding: 8px 10px;
		background: var(--bg-panel);
		border: 1px solid var(--border);
		font-size: 10px;
		letter-spacing: 0.08em;
		color: var(--text-mute);
	}
	label {
		display: inline-flex;
		align-items: center;
		gap: 8px;
	}
	select,
	input[type='range'] {
		accent-color: var(--amber);
		background: var(--bg-elevated);
		border: 1px solid var(--border);
		color: var(--text);
		font-family: var(--font-mono);
		font-size: 11px;
		padding: 2px 6px;
	}
	.v {
		color: var(--cyan);
		min-width: 2.5rem;
	}
	.count {
		margin-left: auto;
		color: var(--amber);
		font-weight: 600;
	}
	.grid {
		display: grid;
		grid-template-columns: 1fr 280px;
		gap: var(--gap);
		min-height: 0;
	}
	.side {
		display: flex;
		flex-direction: column;
		gap: var(--gap);
	}
	.mix {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.mix li {
		display: flex;
		justify-content: space-between;
		padding: 4px 0;
		border-bottom: 1px solid rgba(255, 255, 255, 0.04);
		font-size: 11px;
		color: var(--text-dim);
	}
	.empty {
		color: var(--text-faint);
	}
	@media (max-width: 1000px) {
		.hero {
			grid-template-columns: 1fr 1fr;
		}
		.grid {
			grid-template-columns: 1fr;
		}
	}
</style>
