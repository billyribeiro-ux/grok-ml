<script lang="ts">
	import type { PageData } from './$types';
	import Shell from '$lib/components/Shell.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import { fmtUtcIso } from '$lib/format';

	let { data }: { data: PageData } = $props();
	const flight = $derived(data.flight);
	const laws = $derived(flight?.laws ?? {});
	const meta = $derived(flight?.series?.meta);
	const extra = $derived(flight?.extra ?? {});
	const rs = $derived(data.researchSummary as Record<string, unknown> | null);
	const ranking = $derived(
		((rs?.walkforward_ranking as Record<string, unknown>[]) ?? []) as Record<
			string,
			unknown
		>[]
	);
</script>

<Shell
	flight={flight}
	env={data.env}
	pathUsed={data.pathUsed}
	loadedAt={data.loadedAt}
>
	<div class="page">
		<div class="grid">
			<Panel title="Environment" tag="RUNTIME" accent="cyan">
				<dl class="kv mono">
					<div><dt>ENV</dt><dd class="amber">{data.env}</dd></div>
					<div><dt>TELEMETRY PATH</dt><dd>{data.pathUsed ?? '—'}</dd></div>
					<div><dt>LOADED AT</dt><dd>{fmtUtcIso(data.loadedAt)}</dd></div>
					<div><dt>FLIGHT</dt><dd>{flight?.name ?? '—'}</dd></div>
					<div><dt>SOURCE</dt><dd>{flight?.source ?? '—'}</dd></div>
					<div><dt>WRITTEN</dt><dd>{fmtUtcIso(flight?.written_at)}</dd></div>
					<div>
						<dt>SYMBOLS</dt>
						<dd>{flight?.symbols?.join(' · ') ?? '—'}</dd>
					</div>
				</dl>
			</Panel>

			<Panel title="Series Payload Meta" tag="DENSITY" accent="violet">
				{#if meta}
					<dl class="kv mono">
						<div><dt>EQUITY PTS</dt><dd>{meta.n_equity ?? '—'}</dd></div>
						<div>
							<dt>FILLS</dt>
							<dd>{meta.n_fills_payload}/{meta.n_fills_total}</dd>
						</div>
						<div>
							<dt>SIGNALS</dt>
							<dd>{meta.n_signals_payload}/{meta.n_signals_total}</dd>
						</div>
						<div>
							<dt>REJECTIONS</dt>
							<dd>{meta.n_rejections_payload}/{meta.n_rejections_total}</dd>
						</div>
						<div>
							<dt>OHLC SYMBOLS</dt>
							<dd>{meta.ohlc_symbols?.join(' · ') ?? '—'}</dd>
						</div>
					</dl>
				{:else}
					<p class="pending mono">
						Stats-only flight. Re-run:
						<code>python -m aether.cli engine-flight --lacie</code>
					</p>
				{/if}
				{#if Object.keys(extra).length}
					<h3 class="sub">EXTRA</h3>
					<pre class="pre mono">{JSON.stringify(extra, null, 2)}</pre>
				{/if}
			</Panel>

			<Panel title="Research Snapshot" tag="LOOP STATE" accent="green">
				{#if rs}
					<dl class="kv mono">
						<div>
							<dt>MISSION</dt>
							<dd>{String(rs.mission_flight ?? '—')}</dd>
						</div>
						<div>
							<dt>WINDOW</dt>
							<dd>{String(rs.mission_window ?? '—')}</dd>
						</div>
						<div>
							<dt>LABEL WINNER</dt>
							<dd class="amber">{String(rs.label_winner ?? '—')}</dd>
						</div>
						<div>
							<dt>RECOMMENDED MULTIFOLD</dt>
							<dd class="cyan">{String(rs.recommended_multifold ?? '—')}</dd>
						</div>
						<div>
							<dt>RISK DEFAULT</dt>
							<dd>{JSON.stringify(rs.risk_default ?? {})}</dd>
						</div>
					</dl>
					{#if ranking.length}
						<h3 class="sub">WF RANKING (pct+ · mean sharpe)</h3>
						<ul class="gaps mono">
							{#each ranking.slice(0, 6) as r, i (i)}
								<li>
									<span class="b">{i + 1}</span>
									{String(r.tag)} · pos={r.pct_pos} · sh={r.mean_sharpe} · worst={r.worst}
								</li>
							{/each}
						</ul>
					{/if}
					{#if Array.isArray(rs.honest_notes)}
						<h3 class="sub">HONEST NOTES</h3>
						<ul class="gaps">
							{#each rs.honest_notes as n, i (i)}
								<li><span class="b">◇</span>{String(n)}</li>
							{/each}
						</ul>
					{/if}
				{:else}
					<p class="pending mono">No research_summary.json yet</p>
				{/if}
			</Panel>

			<Panel title="Honest Gaps" tag="L0 TRUTH" accent="amber">
				<ul class="gaps">
					{#each data.gaps as g (g)}
						<li><span class="b">◇</span>{g}</li>
					{/each}
				</ul>
				{#if laws.note}
					<p class="note mono">{laws.note}</p>
				{/if}
			</Panel>

			<Panel title="Constitution" tag="LAWS" accent="green">
				<ul class="laws">
					<li>
						<span class="l">L0</span> Truth — real data or honest gap
						<span class="s {laws.L0_truth ? 'pos' : 'neg'}">{laws.L0_truth ? 'ON' : '—'}</span>
					</li>
					<li>
						<span class="l">L1</span> STAND_DOWN is a successful action
						<span class="s pos">ON</span>
					</li>
					<li>
						<span class="l">L2</span> Human kill-switch remains armed
						<span class="s amber">ARMED</span>
					</li>
					<li>
						<span class="l">L3</span> Money as cents / i64 end-to-end
						<span class="s pos">ON</span>
					</li>
					<li>
						<span class="l">L4</span> No live broker routing in this build
						<span class="s cyan">PAPER</span>
					</li>
					<li>
						<span class="l">L5</span> No fabricated OHLC / PnL for screenshots
						<span class="s pos">ON</span>
					</li>
				</ul>
			</Panel>

			<Panel title="Hotkeys" tag="POWER USER" accent="none">
				<ul class="keys mono">
					<li><kbd>/</kbd> or <kbd>⌘K</kbd> command palette</li>
					<li><kbd>F1–F5</kbd> mission panels (home)</li>
					<li><kbd>1–5</kbd> focus universe symbols (home)</li>
					<li>Nav: Mission · Signals · History · Settings</li>
					<li>API: <code>GET /api/flight</code></li>
				</ul>
			</Panel>

			<Panel title="Rebuild Flight" tag="OPS" accent="red">
				<pre class="pre mono">cd ~/Desktop/grok-ml
.venv/bin/python -m aether.cli engine-flight --lacie \
  --symbols SPY,QQQ,IWM,SQQQ,SH \
  --name lacie_flight

# cockpit
cd apps/cockpit && npm run dev</pre>
			</Panel>
		</div>
	</div>
</Shell>

<style>
	.page {
		padding: var(--gap);
	}
	.grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: var(--gap);
	}
	.kv {
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 10px;
		font-size: 11px;
	}
	.kv dt {
		font-size: 9px;
		letter-spacing: 0.12em;
		color: var(--text-mute);
	}
	.kv dd {
		margin: 0;
		word-break: break-all;
		color: var(--text);
	}
	.gaps {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.gaps li {
		display: flex;
		gap: 8px;
		padding: 6px 0;
		border-bottom: 1px solid rgba(255, 255, 255, 0.04);
		font-size: 12px;
		color: var(--text-dim);
	}
	.b {
		color: var(--amber);
	}
	.note {
		margin-top: 12px;
		padding: 8px;
		border: 1px solid var(--border-amber);
		color: var(--amber);
		font-size: 11px;
	}
	.laws {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.laws li {
		display: grid;
		grid-template-columns: 28px 1fr auto;
		gap: 8px;
		padding: 7px 0;
		border-bottom: 1px solid rgba(255, 255, 255, 0.04);
		font-size: 12px;
		color: var(--text-dim);
		align-items: center;
	}
	.l {
		font-family: var(--font-mono);
		font-weight: 700;
		color: var(--amber);
	}
	.s {
		font-family: var(--font-mono);
		font-size: 10px;
		font-weight: 700;
	}
	.keys {
		list-style: none;
		margin: 0;
		padding: 0;
		font-size: 12px;
		color: var(--text-dim);
		line-height: 1.8;
	}
	kbd {
		background: var(--bg-elevated);
		border: 1px solid var(--border);
		padding: 1px 5px;
		color: var(--amber);
		font-size: 11px;
	}
	.pre {
		margin: 0;
		padding: 10px;
		background: #080c14;
		border: 1px solid var(--border);
		font-size: 11px;
		color: var(--cyan);
		overflow: auto;
		line-height: 1.45;
	}
	.sub {
		margin: 14px 0 6px;
		font-family: var(--font-mono);
		font-size: 10px;
		letter-spacing: 0.12em;
		color: var(--text-mute);
	}
	.pending {
		color: var(--amber);
		font-size: 11px;
	}
	.pending code {
		color: var(--cyan);
	}
	@media (max-width: 900px) {
		.grid {
			grid-template-columns: 1fr;
		}
	}
</style>
