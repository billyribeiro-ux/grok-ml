<script lang="ts">
	import { goto } from '$app/navigation';

	type Cmd = {
		id: string;
		label: string;
		hint: string;
		run: () => void;
	};

	type Props = {
		open: boolean;
		onClose: () => void;
		onPanel?: (id: string) => void;
		symbols?: string[];
		onSymbol?: (s: string) => void;
	};

	let { open, onClose, onPanel, symbols = [], onSymbol }: Props = $props();
	let q = $state('');
	let idx = $state(0);
	let inputEl = $state<HTMLInputElement | null>(null);

	const cmds = $derived.by((): Cmd[] => {
		const base: Cmd[] = [
			{
				id: 'home',
				label: 'Mission Control',
				hint: '/',
				run: () => goto('/')
			},
			{
				id: 'signals',
				label: 'Signal Blotter',
				hint: '/signals',
				run: () => goto('/signals')
			},
			{
				id: 'history',
				label: 'History · Equity · Fills',
				hint: '/history',
				run: () => goto('/history')
			},
			{
				id: 'research',
				label: 'Research · Walk-forward · Risk',
				hint: '/research',
				run: () => goto('/research')
			},
			{
				id: 'data',
				label: 'Data · Archives · Downloads',
				hint: '/data',
				run: () => goto('/data')
			},
			{
				id: 'settings',
				label: 'Settings · Gaps · Laws',
				hint: '/settings',
				run: () => goto('/settings')
			},
			{
				id: 'f1',
				label: 'Panel · Mission',
				hint: 'F1',
				run: () => onPanel?.('MISSION')
			},
			{
				id: 'f2',
				label: 'Panel · Risk',
				hint: 'F2',
				run: () => onPanel?.('RISK')
			},
			{
				id: 'f5',
				label: 'Panel · Honest Gaps',
				hint: 'F5',
				run: () => onPanel?.('GAPS')
			},
			{
				id: 'reload',
				label: 'Hard reload page',
				hint: '↻',
				run: () => location.reload()
			}
		];
		for (const s of symbols) {
			base.push({
				id: `sym-${s}`,
				label: `Focus ${s}`,
				hint: 'universe',
				run: () => onSymbol?.(s)
			});
		}
		const qq = q.trim().toLowerCase();
		if (!qq) return base;
		return base.filter(
			(c) => c.label.toLowerCase().includes(qq) || c.hint.toLowerCase().includes(qq)
		);
	});

	function resetAndFocus() {
		q = '';
		idx = 0;
		queueMicrotask(() => inputEl?.focus());
	}

	// Parent toggles `open`; when dialog mounts, focus search.
	$effect(() => {
		if (!open) return;
		resetAndFocus();
	});

	function run(c: Cmd) {
		c.run();
		onClose();
	}

	function onKey(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			e.preventDefault();
			onClose();
		} else if (e.key === 'ArrowDown') {
			e.preventDefault();
			idx = Math.min(cmds.length - 1, idx + 1);
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			idx = Math.max(0, idx - 1);
		} else if (e.key === 'Enter') {
			e.preventDefault();
			const c = cmds[idx];
			if (c) run(c);
		}
	}
</script>

{#if open}
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div class="backdrop" onclick={onClose} onkeydown={onKey}>
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div
			class="modal"
			role="dialog"
			tabindex="-1"
			aria-modal="true"
			aria-label="Command palette"
			onclick={(e) => e.stopPropagation()}
			onkeydown={onKey}
		>
			<div class="search">
				<span class="slash mono">/</span>
				<input
					bind:this={inputEl}
					bind:value={q}
					placeholder="Jump to panel, route, symbol…"
					autocomplete="off"
					spellcheck="false"
				/>
			</div>
			<ul>
				{#each cmds as c, i (c.id)}
					<li>
						<button type="button" class:active={i === idx} onclick={() => run(c)}>
							<span class="lab">{c.label}</span>
							<span class="hint mono">{c.hint}</span>
						</button>
					</li>
				{/each}
				{#if !cmds.length}
					<li class="none mono">NO MATCH</li>
				{/if}
			</ul>
			<div class="foot mono">↑↓ navigate · enter run · esc close</div>
		</div>
	</div>
{/if}

<style>
	.backdrop {
		position: fixed;
		inset: 0;
		z-index: 10000;
		background: rgba(2, 4, 8, 0.72);
		display: flex;
		align-items: flex-start;
		justify-content: center;
		padding-top: 12vh;
		backdrop-filter: blur(4px);
	}
	.modal {
		width: min(520px, 92vw);
		background: #0b1018;
		border: 1px solid var(--border-amber);
		box-shadow: 0 0 40px rgba(255, 176, 32, 0.12), 0 24px 80px rgba(0, 0, 0, 0.6);
	}
	.search {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 12px 14px;
		border-bottom: 1px solid var(--border);
	}
	.slash {
		color: var(--amber);
		font-size: 16px;
		font-weight: 700;
	}
	input {
		flex: 1;
		background: transparent;
		border: none;
		outline: none;
		color: var(--text);
		font-family: var(--font-mono);
		font-size: 14px;
	}
	ul {
		list-style: none;
		margin: 0;
		padding: 6px;
		max-height: 360px;
		overflow: auto;
	}
	button {
		width: 100%;
		display: flex;
		justify-content: space-between;
		gap: 12px;
		padding: 9px 10px;
		background: transparent;
		border: 1px solid transparent;
		color: var(--text);
		cursor: pointer;
		font: inherit;
		text-align: left;
	}
	button:hover,
	button.active {
		background: rgba(255, 176, 32, 0.08);
		border-color: var(--border-amber);
	}
	.lab {
		font-size: 12px;
	}
	.hint {
		font-size: 10px;
		color: var(--text-mute);
		letter-spacing: 0.06em;
	}
	.none {
		padding: 16px;
		color: var(--text-mute);
		text-align: center;
	}
	.foot {
		padding: 8px 12px;
		border-top: 1px solid var(--border);
		font-size: 9px;
		color: var(--text-faint);
		letter-spacing: 0.08em;
	}
</style>
