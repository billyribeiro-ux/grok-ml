<script lang="ts">
	type Props = {
		symbols: string[];
		selected: string | null;
		source: string;
		onSelect: (sym: string) => void;
	};

	let { symbols, selected, source, onSelect }: Props = $props();

	function role(sym: string): string {
		const s = sym.toUpperCase();
		if (s === 'SPY' || s === 'SPX') return 'BENCH';
		if (s === 'QQQ') return 'NDX';
		if (s === 'IWM') return 'R2K';
		if (s.endsWith('Q') || s === 'SQQQ' || s === 'SH' || s === 'PSQ' || s === 'RWM') return 'INV';
		return 'CORE';
	}
</script>

<div class="rail">
	<div class="head mono">
		<span>UNIVERSE</span>
		<span class="n">{symbols.length}</span>
	</div>
	{#if symbols.length === 0}
		<p class="empty">No symbols in flight payload.</p>
	{:else}
		<ul>
			{#each symbols as sym (sym)}
				<li>
					<button
						type="button"
						class:active={selected === sym}
						onclick={() => onSelect(sym)}
					>
						<span class="sym mono">{sym}</span>
						<span class="role mono">{role(sym)}</span>
						<span class="led" title="From flight telemetry — no live quote"></span>
					</button>
				</li>
			{/each}
		</ul>
	{/if}
	<div class="foot mono">
		SRC · {source || '—'}
		<br />
		NO LIVE QUOTES · TELEMETRY ONLY
	</div>
</div>

<style>
	.rail {
		display: flex;
		flex-direction: column;
		height: 100%;
		min-height: 0;
	}
	.head {
		display: flex;
		justify-content: space-between;
		padding: 0 2px 8px;
		font-size: 10px;
		letter-spacing: 0.14em;
		color: var(--amber);
		font-weight: 600;
	}
	.n {
		color: var(--text-mute);
	}
	ul {
		list-style: none;
		margin: 0;
		padding: 0;
		overflow: auto;
		flex: 1;
	}
	button {
		width: 100%;
		display: grid;
		grid-template-columns: 1fr auto 10px;
		align-items: center;
		gap: 8px;
		padding: 7px 8px;
		margin-bottom: 2px;
		background: var(--bg-elevated);
		border: 1px solid transparent;
		color: var(--text);
		cursor: pointer;
		text-align: left;
		font: inherit;
		border-radius: var(--r);
	}
	button:hover {
		background: var(--bg-hover);
		border-color: var(--border);
	}
	button.active {
		border-color: var(--border-amber);
		background: linear-gradient(90deg, rgba(255, 176, 32, 0.1), var(--bg-elevated));
		box-shadow: inset 2px 0 0 var(--amber);
	}
	.sym {
		font-weight: 700;
		font-size: 12px;
		letter-spacing: 0.04em;
	}
	.role {
		font-size: 9px;
		color: var(--text-mute);
		letter-spacing: 0.08em;
	}
	.led {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background: var(--cyan);
		box-shadow: 0 0 6px var(--cyan);
		opacity: 0.85;
	}
	.empty {
		color: var(--text-mute);
		font-size: 11px;
		padding: 8px;
	}
	.foot {
		margin-top: 8px;
		padding-top: 8px;
		border-top: 1px solid var(--border);
		font-size: 9px;
		line-height: 1.5;
		color: var(--text-faint);
		letter-spacing: 0.04em;
	}
</style>
