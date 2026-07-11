<script lang="ts">
	type Props = {
		label: string;
		value: number;
		max?: number;
		display?: string;
		tone?: 'pos' | 'neg' | 'amber' | 'cyan' | 'violet';
	};

	let { label, value, max = 1, display = '', tone = 'cyan' }: Props = $props();

	const pct = $derived.by(() => {
		if (!max || max <= 0) return 0;
		return Math.min(100, Math.max(0, (value / max) * 100));
	});
</script>

<div class="meter">
	<div class="row">
		<span class="label">{label}</span>
		<span class="val mono {tone}">{display || value}</span>
	</div>
	<div class="track" aria-hidden="true">
		<div class="fill {tone}" style="width: {pct}%"></div>
	</div>
</div>

<style>
	.meter {
		margin-bottom: 7px;
	}
	.meter:last-child {
		margin-bottom: 0;
	}
	.row {
		display: flex;
		justify-content: space-between;
		gap: 8px;
		margin-bottom: 3px;
	}
	.label {
		font-family: var(--font-mono);
		font-size: 10px;
		color: var(--text-dim);
		letter-spacing: 0.04em;
	}
	.val {
		font-size: 10px;
		font-weight: 600;
	}
	.track {
		height: 4px;
		background: #121926;
		border: 1px solid var(--border);
		overflow: hidden;
	}
	.fill {
		height: 100%;
		transition: width 280ms ease;
	}
	.fill.pos {
		background: linear-gradient(90deg, var(--green-dim), var(--green));
		box-shadow: 0 0 8px rgba(0, 230, 118, 0.35);
	}
	.fill.neg {
		background: linear-gradient(90deg, var(--red-dim), var(--red));
		box-shadow: 0 0 8px rgba(255, 59, 69, 0.35);
	}
	.fill.amber {
		background: linear-gradient(90deg, var(--amber-dim), var(--amber));
		box-shadow: 0 0 8px rgba(255, 176, 32, 0.35);
	}
	.fill.cyan {
		background: linear-gradient(90deg, var(--cyan-dim), var(--cyan));
		box-shadow: 0 0 8px rgba(34, 211, 238, 0.3);
	}
	.fill.violet {
		background: linear-gradient(90deg, #6d28d9, var(--violet));
		box-shadow: 0 0 8px rgba(167, 139, 250, 0.3);
	}
</style>
