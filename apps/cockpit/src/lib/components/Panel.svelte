<script lang="ts">
	import type { Snippet } from 'svelte';

	type Props = {
		title: string;
		tag?: string;
		accent?: 'amber' | 'cyan' | 'green' | 'red' | 'violet' | 'none';
		compact?: boolean;
		children: Snippet;
		footer?: Snippet;
	};

	let {
		title,
		tag = '',
		accent = 'none',
		compact = false,
		children,
		footer
	}: Props = $props();
</script>

<section class="panel" class:compact data-accent={accent}>
	<header class="ph">
		<span class="title">{title}</span>
		{#if tag}
			<span class="tag">{tag}</span>
		{/if}
		<span class="glow" aria-hidden="true"></span>
	</header>
	<div class="body">
		{@render children()}
	</div>
	{#if footer}
		<footer class="pf">
			{@render footer()}
		</footer>
	{/if}
</section>

<style>
	.panel {
		display: flex;
		flex-direction: column;
		min-height: 0;
		background:
			linear-gradient(180deg, rgba(255, 176, 32, 0.03) 0%, transparent 28%),
			var(--bg-panel);
		border: 1px solid var(--border);
		border-radius: var(--r);
		overflow: hidden;
		position: relative;
	}
	.panel[data-accent='amber'] {
		border-color: var(--border-amber);
	}
	.panel[data-accent='cyan'] {
		border-color: var(--border-cyan);
	}
	.panel[data-accent='green'] {
		box-shadow: inset 0 0 0 1px rgba(0, 230, 118, 0.12);
	}
	.panel[data-accent='red'] {
		box-shadow: inset 0 0 0 1px rgba(255, 59, 69, 0.14);
	}
	.panel[data-accent='violet'] {
		box-shadow: inset 0 0 0 1px rgba(167, 139, 250, 0.14);
	}
	.ph {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 5px 8px;
		border-bottom: 1px solid var(--border);
		background: linear-gradient(90deg, rgba(255, 176, 32, 0.06), transparent 55%);
		flex-shrink: 0;
		position: relative;
	}
	.title {
		font-family: var(--font-mono);
		font-size: 10px;
		font-weight: 600;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: var(--amber);
	}
	.tag {
		font-family: var(--font-mono);
		font-size: 9px;
		letter-spacing: 0.08em;
		color: var(--text-mute);
		margin-left: auto;
		text-transform: uppercase;
	}
	.glow {
		position: absolute;
		left: 0;
		top: 0;
		bottom: 0;
		width: 2px;
		background: var(--amber);
		opacity: 0.75;
	}
	.body {
		flex: 1;
		min-height: 0;
		padding: 8px;
		overflow: auto;
	}
	.compact .body {
		padding: 6px 8px;
	}
	.pf {
		border-top: 1px solid var(--border);
		padding: 4px 8px;
		font-family: var(--font-mono);
		font-size: 9px;
		color: var(--text-mute);
		flex-shrink: 0;
	}
</style>
