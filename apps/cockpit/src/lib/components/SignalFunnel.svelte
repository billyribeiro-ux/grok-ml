<script lang="ts">
	import { fmtInt } from '$lib/format';

	type Props = {
		nSignals: number;
		nStandDown: number;
		nActionable: number;
		nFills: number;
		nRejections: number;
	};

	let { nSignals, nStandDown, nActionable, nFills, nRejections }: Props = $props();

	const stages = $derived([
		{ key: 'signals', label: 'RAW SIGNALS', n: nSignals, tone: 'cyan' as const },
		{ key: 'stand', label: 'STAND_DOWN', n: nStandDown, tone: 'amber' as const },
		{ key: 'act', label: 'ACTIONABLE', n: nActionable, tone: 'pos' as const },
		{ key: 'fills', label: 'FILLS', n: nFills, tone: 'violet' as const },
		{ key: 'rej', label: 'REJECTIONS', n: nRejections, tone: 'neg' as const }
	]);

	const maxN = $derived(Math.max(1, ...stages.map((s) => s.n)));
</script>

<div class="funnel">
	{#each stages as s (s.key)}
		<div class="stage">
			<div class="meta">
				<span class="lab">{s.label}</span>
				<span class="num mono {s.tone}">{fmtInt(s.n)}</span>
			</div>
			<div class="bar-wrap">
				<div
					class="bar {s.tone}"
					style="width: {(s.n / maxN) * 100}%"
					title="{s.label}: {s.n}"
				></div>
			</div>
			<div class="ratio mono">
				{nSignals > 0 ? ((s.n / nSignals) * 100).toFixed(1) : '—'}% of signals
			</div>
		</div>
	{/each}
</div>

<style>
	.funnel {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	.meta {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		margin-bottom: 3px;
	}
	.lab {
		font-family: var(--font-mono);
		font-size: 10px;
		letter-spacing: 0.1em;
		color: var(--text-dim);
	}
	.num {
		font-size: 14px;
		font-weight: 700;
	}
	.bar-wrap {
		height: 10px;
		background: #0c121c;
		border: 1px solid var(--border);
	}
	.bar {
		height: 100%;
		min-width: 0;
	}
	.bar.cyan {
		background: linear-gradient(90deg, #0e7490, var(--cyan));
	}
	.bar.amber {
		background: linear-gradient(90deg, #92400e, var(--amber));
	}
	.bar.pos {
		background: linear-gradient(90deg, #065f46, var(--green));
	}
	.bar.violet {
		background: linear-gradient(90deg, #5b21b6, var(--violet));
	}
	.bar.neg {
		background: linear-gradient(90deg, #7f1d1d, var(--red));
	}
	.ratio {
		margin-top: 2px;
		font-size: 9px;
		color: var(--text-faint);
	}
</style>
