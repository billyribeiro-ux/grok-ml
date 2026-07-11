<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import type { Snippet } from 'svelte';
	import type { FlightReport } from '$lib/types';
	import {
		fmtEtClock,
		fmtEtDate,
		ageLabel,
		fmtUtcIso
	} from '$lib/format';
	import TickerStrip from '$lib/components/TickerStrip.svelte';
	import CommandPalette from '$lib/components/CommandPalette.svelte';
	import AutoRefresh from '$lib/components/AutoRefresh.svelte';
	import {
		getBook,
		isBookBusy,
		resolveEnv,
		resolveFlight,
		resolvePath,
		selectBook
	} from '$lib/flightBook.svelte';

	type Props = {
		flight: FlightReport | null;
		env: 'SIM' | 'PAPER' | 'OFFLINE';
		pathUsed: string | null;
		loadedAt: string;
		children: Snippet;
		onPanel?: (id: string) => void;
		onSymbol?: (s: string) => void;
		activePanel?: string;
	};

	let {
		flight: flightProp,
		env: envProp,
		pathUsed: pathProp,
		loadedAt,
		children,
		onPanel,
		onSymbol,
		activePanel = ''
	}: Props = $props();

	let nowMs = $state(Date.now());
	let paletteOpen = $state(false);

	const book = $derived(getBook());
	const bookBusy = $derived(isBookBusy());
	const flight = $derived(resolveFlight(flightProp));
	const env = $derived(resolveEnv(envProp));
	const pathUsed = $derived(resolvePath(pathProp));

	const linkLive = $derived(!!flight);
	const telemetryAge = $derived(ageLabel(flight?.written_at, nowMs));
	const symbols = $derived(flight?.symbols ?? []);
	const stats = $derived(flight?.stats ?? {});
	const laws = $derived(flight?.laws ?? {});
	const route = $derived(page.url.pathname);

	const nav = [
		{ href: '/', label: 'MISSION', k: '1' },
		{ href: '/signals', label: 'SIGNALS', k: '2' },
		{ href: '/history', label: 'HISTORY', k: '3' },
		{ href: '/research', label: 'RESEARCH', k: '4' },
		{ href: '/data', label: 'DATA', k: '5' },
		{ href: '/settings', label: 'SETTINGS', k: '6' }
	];

	onMount(() => {
		const t = setInterval(() => {
			nowMs = Date.now();
		}, 1000);
		function onKey(e: KeyboardEvent) {
			if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)
				return;
			if (e.key === '/' && !e.metaKey && !e.ctrlKey) {
				e.preventDefault();
				paletteOpen = true;
			}
			if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
				e.preventDefault();
				paletteOpen = true;
			}
		}
		window.addEventListener('keydown', onKey);
		return () => {
			clearInterval(t);
			window.removeEventListener('keydown', onKey);
		};
	});
</script>

<div class="terminal">
	<header class="topbar">
		<div class="brand-block">
			<div class="mark">AETHER</div>
			<div class="product mono">TERMINAL · MARS-GRADE</div>
		</div>

		<div class="env-pill mono" data-env={env}>
			<span class="dot"></span>
			{env}
		</div>

		<div class="book-switch mono" role="group" aria-label="Telemetry book">
			<button
				type="button"
				class:active={book === 'mission'}
				disabled={bookBusy}
				onclick={() => selectBook('mission')}
				title="Mission dashboard telemetry (lacie_best_risk)"
			>
				MISSION
			</button>
			<button
				type="button"
				class:active={book === 'recommended'}
				disabled={bookBusy}
				onclick={() => selectBook('recommended')}
				title="Research recommended book (hybrid_plus_mega c58 p3)"
			>
				RESEARCH
			</button>
		</div>

		<nav class="nav mono" aria-label="Primary">
			{#each nav as n (n.href)}
				<a href={n.href} class:active={route === n.href || (n.href !== '/' && route.startsWith(n.href))}>
					<span class="nk">{n.k}</span>
					{n.label}
				</a>
			{/each}
		</nav>

		<div class="meta-cluster mono">
			<div class="meta-item">
				<span class="k">ET</span>
				<span class="v amber">{fmtEtClock(nowMs)}</span>
			</div>
			<div class="meta-item">
				<span class="k">DATE</span>
				<span class="v">{fmtEtDate(nowMs)}</span>
			</div>
			<div class="meta-item">
				<span class="k">LINK</span>
				<span class="v {linkLive ? 'pos' : 'neg'}">{linkLive ? 'HOT' : 'COLD'}</span>
			</div>
			<div class="meta-item">
				<span class="k">AGE</span>
				<span class="v cyan">{telemetryAge}</span>
			</div>
			<div class="meta-item">
				<span class="k">L0</span>
				<span class="v {laws.L0_truth ? 'pos' : 'neg'}">
					{laws.L0_truth ? 'TRUTH' : '—'}
				</span>
			</div>
		</div>

		<AutoRefresh intervalSec={45} />

		<button type="button" class="cmd mono" onclick={() => (paletteOpen = true)} title="Command palette (/)">
			/
		</button>

		<div class="heartbeat mono">
			<span class="pulse" class:on={linkLive}></span>
			HB
		</div>
	</header>

	{#if flight}
		<TickerStrip symbols={symbols} stats={stats} flightName={flight.name} />
	{:else}
		<div class="ticker-empty mono">
			NO TELEMETRY · run <code>python -m aether.cli engine-flight --lacie</code>
		</div>
	{/if}

	<main class="main">
		{@render children()}
	</main>

	<footer class="statusbar mono">
		<span class="seg">
			<span class="sk">ROUTE</span>
			<span class="sv cyan">{route}</span>
		</span>
		<span class="div">│</span>
		<span class="seg">
			<span class="sk">SRC</span>
			<span class="sv">{flight?.source ?? '—'}</span>
		</span>
		<span class="div">│</span>
		<span class="seg">
			<span class="sk">PATH</span>
			<span class="sv dim">{pathUsed ? pathUsed.split('/').slice(-3).join('/') : '—'}</span>
		</span>
		<span class="div">│</span>
		<span class="seg">
			<span class="sk">LOAD</span>
			<span class="sv dim">{fmtUtcIso(loadedAt)}</span>
		</span>
		{#if activePanel}
			<span class="div">│</span>
			<span class="seg">
				<span class="sk">PANEL</span>
				<span class="sv amber">{activePanel}</span>
			</span>
		{/if}
		<span class="div">│</span>
		<span class="seg grow">
			<span class="sk">AETHER</span>
			<span class="sv">BEYOND INSTITUTION · PRESS / · TELEMETRY-BOUND</span>
		</span>
	</footer>
</div>

<CommandPalette
	open={paletteOpen}
	onClose={() => (paletteOpen = false)}
	{onPanel}
	{symbols}
	{onSymbol}
/>

<style>
	.terminal {
		height: 100vh;
		height: 100dvh;
		display: grid;
		grid-template-rows: var(--header-h) auto 1fr var(--status-h);
		background: var(--bg-void);
		overflow: hidden;
	}
	.topbar {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 0 12px;
		background: linear-gradient(180deg, #0c121c 0%, #070b12 100%);
		border-bottom: 1px solid var(--border-bright);
	}
	.brand-block {
		display: flex;
		align-items: baseline;
		gap: 8px;
	}
	.mark {
		font-family: var(--font-mono);
		font-weight: 700;
		font-size: 14px;
		letter-spacing: 0.28em;
		color: var(--amber);
		text-shadow: 0 0 18px rgba(255, 176, 32, 0.45);
	}
	.product {
		font-size: 9px;
		letter-spacing: 0.14em;
		color: var(--text-mute);
	}
	.env-pill {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 3px 10px;
		border: 1px solid var(--border-amber);
		background: rgba(255, 176, 32, 0.08);
		color: var(--amber);
		font-size: 10px;
		font-weight: 700;
		letter-spacing: 0.16em;
	}
	.env-pill[data-env='SIM'] {
		border-color: rgba(34, 211, 238, 0.35);
		background: rgba(34, 211, 238, 0.08);
		color: var(--cyan);
	}
	.env-pill[data-env='OFFLINE'] {
		border-color: rgba(255, 59, 69, 0.4);
		color: var(--red);
		background: rgba(255, 59, 69, 0.08);
	}
	.env-pill .dot {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background: currentColor;
		box-shadow: 0 0 8px currentColor;
		animation: blink 1.4s step-end infinite;
	}
	.book-switch {
		display: inline-flex;
		border: 1px solid var(--border);
		background: #080c14;
	}
	.book-switch button {
		appearance: none;
		border: 0;
		background: transparent;
		color: var(--text-mute);
		font: inherit;
		font-size: 9px;
		font-weight: 700;
		letter-spacing: 0.12em;
		padding: 4px 8px;
		cursor: pointer;
	}
	.book-switch button + button {
		border-left: 1px solid var(--border);
	}
	.book-switch button.active {
		color: var(--cyan);
		background: rgba(34, 211, 238, 0.1);
		text-shadow: 0 0 10px rgba(34, 211, 238, 0.35);
	}
	.book-switch button:disabled {
		opacity: 0.55;
		cursor: wait;
	}
	.nav {
		display: flex;
		gap: 2px;
		margin-left: 8px;
	}
	.nav a {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		padding: 4px 8px;
		color: var(--text-mute);
		text-decoration: none;
		font-size: 10px;
		letter-spacing: 0.1em;
		border: 1px solid transparent;
	}
	.nav a:hover {
		color: var(--text);
		background: var(--bg-hover);
	}
	.nav a.active {
		color: var(--amber);
		border-color: var(--border-amber);
		background: rgba(255, 176, 32, 0.08);
	}
	.nk {
		color: var(--text-faint);
		font-size: 9px;
	}
	.meta-cluster {
		display: flex;
		gap: 12px;
		margin-left: auto;
	}
	.meta-item {
		display: flex;
		flex-direction: column;
		gap: 1px;
	}
	.meta-item .k {
		font-size: 8px;
		letter-spacing: 0.14em;
		color: var(--text-faint);
	}
	.meta-item .v {
		font-size: 11px;
		font-weight: 600;
	}
	.cmd {
		background: var(--bg-elevated);
		border: 1px solid var(--border);
		color: var(--amber);
		width: 28px;
		height: 24px;
		cursor: pointer;
		font-weight: 700;
	}
	.cmd:hover {
		border-color: var(--border-amber);
	}
	.heartbeat {
		display: flex;
		align-items: center;
		gap: 6px;
		font-size: 10px;
		color: var(--text-mute);
	}
	.pulse {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--text-faint);
	}
	.pulse.on {
		background: var(--green);
		box-shadow: 0 0 10px var(--green);
		animation: blink 1s step-end infinite;
	}
	@keyframes blink {
		50% {
			opacity: 0.25;
		}
	}
	.ticker-empty {
		height: var(--ticker-h);
		display: flex;
		align-items: center;
		padding: 0 12px;
		background: #04070c;
		border-bottom: 1px solid var(--border);
		color: var(--amber);
		font-size: 11px;
		gap: 6px;
	}
	.ticker-empty code {
		color: var(--cyan);
	}
	.main {
		min-height: 0;
		overflow: auto;
		background: var(--bg-deep);
	}
	.statusbar {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 0 10px;
		background: #04070c;
		border-top: 1px solid var(--border-bright);
		font-size: 10px;
		overflow: hidden;
		white-space: nowrap;
	}
	.seg {
		display: inline-flex;
		gap: 6px;
	}
	.seg.grow {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.sk {
		color: var(--text-faint);
		letter-spacing: 0.1em;
	}
	.sv {
		font-weight: 600;
	}
	.sv.dim {
		color: var(--text-mute);
		font-weight: 400;
		font-size: 9px;
	}
	.div {
		color: var(--text-faint);
		opacity: 0.5;
	}
	@media (max-width: 1100px) {
		.product,
		.meta-item:nth-child(2) {
			display: none;
		}
	}
	@media (max-width: 800px) {
		.nav {
			display: none;
		}
	}
</style>
