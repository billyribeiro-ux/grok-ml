<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import { onMount } from 'svelte';

	type Props = {
		/** seconds between soft reloads of load functions */
		intervalSec?: number;
		enabled?: boolean;
	};

	let { intervalSec = 45, enabled = true }: Props = $props();
	let last = $state<string>('—');
	let busy = $state(false);
	let err = $state('');

	async function tick() {
		if (!enabled || busy) return;
		busy = true;
		err = '';
		try {
			await invalidateAll();
			last = new Date().toLocaleTimeString('en-US', {
				hour12: false,
				timeZone: 'America/New_York'
			});
		} catch (e) {
			err = e instanceof Error ? e.message : 'refresh failed';
		} finally {
			busy = false;
		}
	}

	onMount(() => {
		const ms = Math.max(10, intervalSec) * 1000;
		const id = setInterval(tick, ms);
		return () => clearInterval(id);
	});
</script>

<div class="ar mono" title="Soft-reloads SvelteKit load() for latest telemetry">
	<button type="button" onclick={tick} disabled={busy}>
		{busy ? '…' : '↻'}
	</button>
	<span class="lab">POLL {intervalSec}s</span>
	<span class="last">ET {last}</span>
	{#if err}
		<span class="err">{err}</span>
	{/if}
</div>

<style>
	.ar {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		font-size: 9px;
		letter-spacing: 0.08em;
		color: var(--text-mute);
	}
	button {
		background: var(--bg-elevated);
		border: 1px solid var(--border);
		color: var(--cyan);
		width: 22px;
		height: 20px;
		cursor: pointer;
		font-size: 12px;
		padding: 0;
	}
	button:hover:not(:disabled) {
		border-color: var(--border-cyan);
	}
	button:disabled {
		opacity: 0.5;
	}
	.last {
		color: var(--text-faint);
	}
	.err {
		color: var(--red);
		max-width: 120px;
		overflow: hidden;
		text-overflow: ellipsis;
	}
</style>
