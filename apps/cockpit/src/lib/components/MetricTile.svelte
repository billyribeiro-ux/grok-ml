<script lang="ts">
	type Props = {
		label: string;
		value: string;
		sub?: string;
		tone?: 'pos' | 'neg' | 'neu' | 'amber' | 'cyan';
		large?: boolean;
	};

	let { label, value, sub = '', tone = 'neu', large = false }: Props = $props();
</script>

<div class="tile" class:large>
	<div class="label">{label}</div>
	<div class="value {tone} mono">{value}</div>
	{#if sub}
		<div class="sub mono">{sub}</div>
	{/if}
</div>

<style>
	.tile {
		padding: 6px 8px;
		background: var(--bg-elevated);
		border: 1px solid var(--border);
		border-radius: var(--r);
		min-width: 0;
	}
	.tile.large {
		padding: 10px 12px;
	}
	.label {
		font-family: var(--font-mono);
		font-size: 9px;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--text-mute);
		margin-bottom: 4px;
	}
	.value {
		font-size: 16px;
		font-weight: 600;
		letter-spacing: -0.01em;
		line-height: 1.1;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.large .value {
		font-size: 22px;
	}
	.sub {
		margin-top: 3px;
		font-size: 10px;
		color: var(--text-mute);
	}
</style>
