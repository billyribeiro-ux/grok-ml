<script lang="ts">
	import type { CalibrationBin } from '$lib/types';
	import { fmtNum } from '$lib/format';

	type Props = {
		bins: CalibrationBin[];
		brier?: number | null;
	};

	let { bins, brier = null }: Props = $props();

	const usable = $derived(bins.filter((b) => b.n > 0 && b.avg_p != null && b.avg_y != null));
</script>

<div class="cal">
	<div class="head mono">
		<span>RELIABILITY</span>
		<span class="brier">BRIER {brier != null ? fmtNum(brier, 4) : '—'}</span>
	</div>
	{#if !usable.length}
		<p class="empty mono">NO CALIBRATION BINS</p>
	{:else}
		<svg viewBox="0 0 220 160" class="plot" aria-label="Calibration reliability diagram">
			<!-- axes -->
			<line x1="30" y1="10" x2="30" y2="130" class="axis" />
			<line x1="30" y1="130" x2="200" y2="130" class="axis" />
			<!-- diagonal perfect -->
			<line x1="30" y1="130" x2="200" y2="10" class="perfect" />
			{#each usable as b, i (i)}
				{@const x = 30 + (b.avg_p as number) * 170}
				{@const y = 130 - (b.avg_y as number) * 120}
				{@const r = 3 + Math.min(8, Math.sqrt(b.n))}
				<circle cx={x} cy={y} r={r} class="dot" />
				<title>
					p={fmtNum(b.avg_p, 3)} y={fmtNum(b.avg_y, 3)} n={b.n}
				</title>
			{/each}
			<text x="110" y="148" text-anchor="middle" class="lbl">predicted p</text>
			<text x="12" y="70" text-anchor="middle" class="lbl" transform="rotate(-90 12 70)">
				realized
			</text>
		</svg>
		<ul class="bins">
			{#each usable as b, i (i)}
				<li class="mono">
					[{fmtNum(b.lo, 1)}–{fmtNum(b.hi, 1)}] n={b.n} p={fmtNum(b.avg_p, 3)} y={fmtNum(
						b.avg_y,
						3
					)}
				</li>
			{/each}
		</ul>
	{/if}
</div>

<style>
	.cal {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 8px;
		align-items: start;
	}
	.head {
		grid-column: 1 / -1;
		display: flex;
		justify-content: space-between;
		font-size: 10px;
		letter-spacing: 0.12em;
		color: var(--text-mute);
	}
	.brier {
		color: var(--cyan);
		font-weight: 600;
	}
	.plot {
		width: 100%;
		max-width: 240px;
		background: #080c14;
		border: 1px solid var(--border);
	}
	.axis {
		stroke: #2a3548;
		stroke-width: 1;
	}
	.perfect {
		stroke: rgba(255, 176, 32, 0.35);
		stroke-width: 1;
		stroke-dasharray: 4 3;
	}
	.dot {
		fill: var(--cyan);
		stroke: #0a0e16;
		stroke-width: 1;
		filter: drop-shadow(0 0 3px var(--cyan));
	}
	.lbl {
		fill: var(--text-faint);
		font-family: var(--font-mono);
		font-size: 8px;
		letter-spacing: 0.06em;
	}
	.bins {
		list-style: none;
		margin: 0;
		padding: 0;
		max-height: 150px;
		overflow: auto;
		font-size: 9px;
		color: var(--text-dim);
	}
	.bins li {
		padding: 2px 0;
		border-bottom: 1px solid rgba(255, 255, 255, 0.03);
	}
	.empty {
		grid-column: 1 / -1;
		color: var(--amber);
		font-size: 11px;
	}
	@media (max-width: 700px) {
		.cal {
			grid-template-columns: 1fr;
		}
	}
</style>
