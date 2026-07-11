<script lang="ts">
	import { onMount } from 'svelte';
	import type { OhlcBar } from '$lib/types';

	type Props = {
		symbol: string;
		bars: OhlcBar[];
		height?: number;
	};

	let { symbol, bars, height = 240 }: Props = $props();
	let el = $state<HTMLDivElement | null>(null);
	let status = $state('init');

	onMount(() => {
		let disposed = false;
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		let chart: any = null;
		let ro: ResizeObserver | null = null;

		async function boot() {
			if (!el || !bars.length) {
				status = 'empty';
				return;
			}
			const lc = await import('lightweight-charts');
			if (disposed || !el) return;

			const hasOHLC = bars.some((b) => b.open != null && b.high != null && b.low != null);

			chart = lc.createChart(el, {
				height,
				layout: {
					background: { type: lc.ColorType.Solid, color: '#0a0e16' },
					textColor: '#8b97a8',
					fontFamily: "'IBM Plex Mono', monospace",
					fontSize: 10
				},
				grid: {
					vertLines: { color: 'rgba(120,160,220,0.05)' },
					horzLines: { color: 'rgba(120,160,220,0.05)' }
				},
				rightPriceScale: { borderColor: 'rgba(120,160,220,0.12)' },
				timeScale: { borderColor: 'rgba(120,160,220,0.12)' },
				crosshair: {
					vertLine: { color: 'rgba(255,176,32,0.3)', labelBackgroundColor: '#ffb020' },
					horzLine: { color: 'rgba(0,230,118,0.3)', labelBackgroundColor: '#065f46' }
				}
			});

			if (hasOHLC) {
				const candle = chart.addCandlestickSeries({
					upColor: '#00e676',
					downColor: '#ff3b45',
					borderUpColor: '#00e676',
					borderDownColor: '#ff3b45',
					wickUpColor: '#00e676',
					wickDownColor: '#ff3b45'
				});
				candle.setData(
					bars
						.filter((b) => b.open != null && b.high != null && b.low != null)
						.map((b) => ({
							time: b.date,
							open: b.open as number,
							high: b.high as number,
							low: b.low as number,
							close: b.close
						}))
				);
			} else {
				const line = chart.addLineSeries({ color: '#ffb020', lineWidth: 2 });
				line.setData(bars.map((b) => ({ time: b.date, value: b.close })));
			}

			if (bars.some((b) => b.volume != null)) {
				const vol = chart.addHistogramSeries({
					priceFormat: { type: 'volume' },
					priceScaleId: 'vol',
					color: 'rgba(79,140,255,0.45)'
				});
				chart.priceScale('vol').applyOptions({
					scaleMargins: { top: 0.8, bottom: 0 }
				});
				vol.setData(
					bars
						.filter((b) => b.volume != null)
						.map((b) => ({
							time: b.date,
							value: b.volume as number,
							color:
								(b.close ?? 0) >= (b.open ?? b.close)
									? 'rgba(0,230,118,0.35)'
									: 'rgba(255,59,69,0.35)'
						}))
				);
			}

			chart.timeScale().fitContent();
			status = hasOHLC ? 'ohlc' : 'close-only';
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
	{#if !bars.length}
		<div class="empty mono">NO BARS · {symbol}</div>
	{:else}
		<div class="chart" bind:this={el}></div>
		<div class="badge mono">{symbol} · {bars.length} BARS · {status} · OOS TELEMETRY</div>
	{/if}
</div>

<style>
	.wrap {
		position: relative;
		width: 100%;
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
		font-size: 11px;
		letter-spacing: 0.1em;
		border: 1px dashed var(--border);
	}
	.badge {
		position: absolute;
		top: 6px;
		left: 8px;
		font-size: 9px;
		letter-spacing: 0.08em;
		color: var(--text-mute);
		pointer-events: none;
	}
</style>
