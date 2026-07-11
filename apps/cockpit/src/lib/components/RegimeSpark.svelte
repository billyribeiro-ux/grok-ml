<script lang="ts">
	type Point = {
		date: string;
		trend_energy?: number;
		breadth_integrity?: number;
		vol_regime?: number;
		uncertainty?: number;
	};

	type Props = {
		points: Point[];
		height?: number;
	};

	let { points, height = 64 }: Props = $props();

	const series = $derived.by(() => {
		const keys = ['breadth_integrity', 'vol_regime', 'uncertainty', 'trend_energy'] as const;
		const w = 320;
		const h = height;
		const n = points.length;
		if (n < 2) return [] as { key: string; d: string; color: string }[];
		const colors: Record<string, string> = {
			breadth_integrity: '#22d3ee',
			vol_regime: '#ffb020',
			uncertainty: '#ff3b45',
			trend_energy: '#00e676'
		};
		return keys.map((key) => {
			const vals = points.map((p) => {
				const v = p[key];
				if (v == null || Number.isNaN(v)) return 0.5;
				// trend_energy is -1..1 → 0..1
				if (key === 'trend_energy') return (Number(v) + 1) / 2;
				return Math.min(1, Math.max(0, Number(v)));
			});
			const d = vals
				.map((v, i) => {
					const x = (i / (n - 1)) * w;
					const y = h - 4 - v * (h - 8);
					return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
				})
				.join(' ');
			return { key, d, color: colors[key] };
		});
	});
</script>

{#if points.length < 2}
	<p class="empty mono">NO REGIME SERIES</p>
{:else}
	<svg viewBox="0 0 320 {height}" class="spark" preserveAspectRatio="none" aria-label="Regime sparkline">
		{#each series as s (s.key)}
			<path d={s.d} fill="none" stroke={s.color} stroke-width="1.5" opacity="0.9" />
		{/each}
	</svg>
	<div class="legend mono">
		<span class="c cyan">BREADTH</span>
		<span class="c amber">VOL</span>
		<span class="c neg">UNC</span>
		<span class="c pos">TREND</span>
		<span class="n">{points.length}d</span>
	</div>
{/if}

<style>
	.spark {
		width: 100%;
		height: auto;
		display: block;
		background: #080c14;
		border: 1px solid var(--border);
	}
	.legend {
		display: flex;
		gap: 10px;
		margin-top: 4px;
		font-size: 9px;
		letter-spacing: 0.08em;
		color: var(--text-mute);
	}
	.n {
		margin-left: auto;
		color: var(--text-faint);
	}
	.empty {
		color: var(--amber);
		font-size: 11px;
	}
</style>
