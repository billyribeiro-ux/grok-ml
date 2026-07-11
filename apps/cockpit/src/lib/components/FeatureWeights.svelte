<script lang="ts">
	import type { FeatureWeight } from '$lib/types';
	import { fmtNum } from '$lib/format';

	type Props = {
		weights: FeatureWeight[];
		max?: number;
	};

	let { weights, max = 14 }: Props = $props();

	const top = $derived(weights.slice(0, max));
	const maxAbs = $derived(Math.max(1e-9, ...top.map((w) => w.abs_weight)));
</script>

{#if !top.length}
	<p class="empty mono">NO FEATURE WEIGHTS IN TELEMETRY</p>
{:else}
	<ul class="list">
		{#each top as w (w.feature)}
			<li>
				<div class="row">
					<span class="name mono">{w.feature}</span>
					<span class="val mono {w.weight >= 0 ? 'pos' : 'neg'}">{fmtNum(w.weight, 4)}</span>
				</div>
				<div class="track" aria-hidden="true">
					<div
						class="fill {w.weight >= 0 ? 'pos' : 'neg'}"
						style="width: {(w.abs_weight / maxAbs) * 100}%"
					></div>
				</div>
			</li>
		{/each}
	</ul>
{/if}

<style>
	.list {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.row {
		display: flex;
		justify-content: space-between;
		gap: 8px;
		margin-bottom: 2px;
	}
	.name {
		font-size: 10px;
		color: var(--text-dim);
		letter-spacing: 0.04em;
	}
	.val {
		font-size: 10px;
		font-weight: 700;
	}
	.track {
		height: 3px;
		background: #121926;
		border: 1px solid var(--border);
		margin-bottom: 7px;
	}
	.fill {
		height: 100%;
	}
	.fill.pos {
		background: linear-gradient(90deg, #065f46, var(--green));
	}
	.fill.neg {
		background: linear-gradient(90deg, #7f1d1d, var(--red));
	}
	.empty {
		color: var(--amber);
		font-size: 11px;
		padding: 8px 0;
	}
</style>
