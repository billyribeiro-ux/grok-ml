<script lang="ts">
	import { onMount } from 'svelte';
	import type { EquityPoint } from '$lib/types';

	type Props = {
		points: EquityPoint[];
		height?: number;
	};

	let { points, height = 220 }: Props = $props();
	let el = $state<HTMLDivElement | null>(null);
	let status = $state('init');

	onMount(() => {
		let disposed = false;
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		let chart: any = null;
		let ro: ResizeObserver | null = null;

		async function boot() {
			if (!el || !points.length) {
				status = points.length ? 'no-el' : 'empty';
				return;
			}
			const lc = await import('lightweight-charts');
			if (disposed || !el) return;

			chart = lc.createChart(el, {
				height,
				layout: {
					background: { type: lc.ColorType.Solid, color: '#0a0e16' },
					textColor: '#8b97a8',
					fontFamily: "'IBM Plex Mono', monospace",
					fontSize: 10
				},
				grid: {
					vertLines: { color: 'rgba(120,160,220,0.06)' },
					horzLines: { color: 'rgba(120,160,220,0.06)' }
				},
				rightPriceScale: {
					borderColor: 'rgba(120,160,220,0.12)',
					scaleMargins: { top: 0.12, bottom: 0.18 }
				},
				timeScale: {
					borderColor: 'rgba(120,160,220,0.12)'
				},
				crosshair: {
					vertLine: { color: 'rgba(255,176,32,0.35)', labelBackgroundColor: '#ffb020' },
					horzLine: { color: 'rgba(34,211,238,0.35)', labelBackgroundColor: '#0e7490' }
				}
			});

			const area = chart.addAreaSeries({
				lineColor: '#22d3ee',
				topColor: 'rgba(34, 211, 238, 0.28)',
				bottomColor: 'rgba(34, 211, 238, 0.01)',
				lineWidth: 2,
				priceLineVisible: false,
				lastValueVisible: true
			});

			const dd = chart.addLineSeries({
				color: '#ff3b45',
				lineWidth: 1,
				priceScaleId: 'dd',
				priceLineVisible: false,
				lastValueVisible: false
			});
			chart.priceScale('dd').applyOptions({
				scaleMargins: { top: 0.82, bottom: 0 },
				borderVisible: false
			});

			area.setData(points.map((p) => ({ time: p.date, value: p.equity_usd })));
			dd.setData(
				points
					.filter((p) => p.drawdown != null)
					.map((p) => ({ time: p.date, value: -((p.drawdown ?? 0) * 100) }))
			);

			chart.timeScale().fitContent();
			status = 'ok';

			ro = new ResizeObserver(() => {
				if (el && chart) chart.applyOptions({ width: el.clientWidth });
			});
			ro.observe(el);
			chart.applyOptions({ width: el.clientWidth });
		}

		boot();
		return () => {
			disposed = true;
			ro?.disconnect();
			chart?.remove();
		};
	});
</script>

<div class="wrap" style:height="{height}px">
	{#if !points.length}
		<div class="empty mono">NO EQUITY CURVE IN TELEMETRY</div>
	{:else}
		<div class="chart" bind:this={el}></div>
		<div class="badge mono">EQUITY USD · DD% (red) · {points.length} pts · {status}</div>
	{/if}
</div>

<style>
	.wrap {
		position: relative;
		width: 100%;
		min-height: 120px;
	}
	.chart {
		width: 100%;
		height: 100%;
	}
	.empty {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 100%;
		color: var(--amber);
		letter-spacing: 0.1em;
		font-size: 11px;
		border: 1px dashed var(--border);
		background: var(--bg-elevated);
	}
	.badge {
		position: absolute;
		top: 6px;
		left: 8px;
		font-size: 9px;
		letter-spacing: 0.08em;
		color: var(--text-mute);
		pointer-events: none;
		text-shadow: 0 0 8px #0a0e16;
	}
</style>
