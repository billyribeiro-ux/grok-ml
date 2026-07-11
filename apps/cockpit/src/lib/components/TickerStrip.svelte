<script lang="ts">
	import { fmtPct, fmtNum, fmtUsd, signClass } from '$lib/format';
	import type { FlightStats } from '$lib/types';

	type Props = {
		symbols: string[];
		stats: FlightStats;
		flightName: string;
	};

	let { symbols, stats, flightName }: Props = $props();

	const chips = $derived([
		{ k: 'FLIGHT', v: flightName || '—', tone: 'amber' as const },
		{ k: 'RET', v: fmtPct(stats.total_return), tone: signClass(stats.total_return) },
		{ k: 'SHARPE', v: fmtNum(stats.sharpe_like, 3), tone: 'cyan' as const },
		{ k: 'MAXDD', v: fmtPct(stats.max_drawdown), tone: 'neg' as const },
		{ k: 'VOL', v: fmtPct(stats.ann_vol), tone: 'amber' as const },
		{ k: 'EQ', v: fmtUsd(stats.final_equity_usd), tone: 'pos' as const },
		{ k: 'FILLS', v: String(stats.n_fills ?? '—'), tone: 'neu' as const },
		{ k: 'SIG', v: String(stats.n_signals ?? '—'), tone: 'neu' as const },
		{
			k: 'UNIVERSE',
			v: symbols.length ? symbols.join(' · ') : '—',
			tone: 'cyan' as const
		}
	]);
</script>

<div class="strip" role="marquee" aria-label="Flight summary ticker">
	<div class="track">
		{#each [...chips, ...chips] as c, i (`${c.k}-${i}`)}
			<span class="chip">
				<span class="k">{c.k}</span>
				<span class="v mono {c.tone}">{c.v}</span>
			</span>
			<span class="sep" aria-hidden="true">◆</span>
		{/each}
	</div>
</div>

<style>
	.strip {
		height: var(--ticker-h);
		background: #04070c;
		border-bottom: 1px solid var(--border);
		overflow: hidden;
		display: flex;
		align-items: center;
		position: relative;
	}
	.strip::before,
	.strip::after {
		content: '';
		position: absolute;
		top: 0;
		bottom: 0;
		width: 40px;
		z-index: 2;
		pointer-events: none;
	}
	.strip::before {
		left: 0;
		background: linear-gradient(90deg, #04070c, transparent);
	}
	.strip::after {
		right: 0;
		background: linear-gradient(270deg, #04070c, transparent);
	}
	.track {
		display: flex;
		align-items: center;
		gap: 0;
		white-space: nowrap;
		animation: scroll 48s linear infinite;
		padding-left: 100%;
	}
	.chip {
		display: inline-flex;
		align-items: baseline;
		gap: 6px;
		padding: 0 10px;
	}
	.k {
		font-family: var(--font-mono);
		font-size: 9px;
		letter-spacing: 0.12em;
		color: var(--text-mute);
	}
	.v {
		font-size: 11px;
		font-weight: 600;
	}
	.sep {
		color: var(--text-faint);
		font-size: 7px;
		opacity: 0.6;
	}
	@keyframes scroll {
		from {
			transform: translateX(0);
		}
		to {
			transform: translateX(-50%);
		}
	}
</style>
