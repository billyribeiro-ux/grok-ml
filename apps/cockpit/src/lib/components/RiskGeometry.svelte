<script lang="ts">
	import { fmtPct, fmtNum, clamp01 } from '$lib/format';

	type Props = {
		maxDrawdown: number | null | undefined;
		annVol: number | null | undefined;
		sharpe: number | null | undefined;
		totalReturn: number | null | undefined;
	};

	let { maxDrawdown, annVol, sharpe, totalReturn }: Props = $props();

	/** Visual rings from real summary stats — not a fabricated equity path. */
	const ddArc = $derived(clamp01(maxDrawdown ?? 0) * 100);
	const volArc = $derived(clamp01((annVol ?? 0) / 0.5) * 100);
	const sharpeArc = $derived(clamp01(((sharpe ?? 0) + 1) / 3) * 100);
	const retArc = $derived(clamp01(Math.abs(totalReturn ?? 0) / 0.5) * 100);

	function ring(pct: number, r: number, color: string): string {
		const c = 2 * Math.PI * r;
		const dash = (pct / 100) * c;
		return `stroke-dasharray: ${dash} ${c}; stroke: ${color}`;
	}
</script>

<div class="geo">
	<svg viewBox="0 0 160 160" class="rings" aria-label="Risk geometry from flight stats">
		<circle class="track" cx="80" cy="80" r="68" />
		<circle class="track" cx="80" cy="80" r="54" />
		<circle class="track" cx="80" cy="80" r="40" />
		<circle class="track" cx="80" cy="80" r="26" />

		<circle
			class="arc"
			cx="80"
			cy="80"
			r="68"
			style={ring(ddArc, 68, 'var(--red)')}
			transform="rotate(-90 80 80)"
		/>
		<circle
			class="arc"
			cx="80"
			cy="80"
			r="54"
			style={ring(volArc, 54, 'var(--amber)')}
			transform="rotate(-90 80 80)"
		/>
		<circle
			class="arc"
			cx="80"
			cy="80"
			r="40"
			style={ring(sharpeArc, 40, 'var(--cyan)')}
			transform="rotate(-90 80 80)"
		/>
		<circle
			class="arc"
			cx="80"
			cy="80"
			r="26"
			style={ring(retArc, 26, 'var(--green)')}
			transform="rotate(-90 80 80)"
		/>
		<text x="80" y="76" text-anchor="middle" class="hub-label">SHARPE</text>
		<text x="80" y="94" text-anchor="middle" class="hub-val">{fmtNum(sharpe, 3)}</text>
	</svg>

	<ul class="legend">
		<li><i class="sw red"></i> MAX DD <span class="mono neg">{fmtPct(maxDrawdown)}</span></li>
		<li><i class="sw amber"></i> ANN VOL <span class="mono amber">{fmtPct(annVol)}</span></li>
		<li><i class="sw cyan"></i> SHARPE <span class="mono cyan">{fmtNum(sharpe, 3)}</span></li>
		<li>
			<i class="sw green"></i> TOT RET
			<span class="mono { (totalReturn ?? 0) >= 0 ? 'pos' : 'neg' }">{fmtPct(totalReturn)}</span>
		</li>
	</ul>
</div>

<style>
	.geo {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 8px;
		align-items: center;
	}
	.rings {
		width: 100%;
		max-width: 180px;
		margin: 0 auto;
		display: block;
	}
	.track {
		fill: none;
		stroke: #1a2436;
		stroke-width: 7;
	}
	.arc {
		fill: none;
		stroke-width: 7;
		stroke-linecap: butt;
		filter: drop-shadow(0 0 3px currentColor);
	}
	.hub-label {
		fill: var(--text-mute);
		font-family: var(--font-mono);
		font-size: 8px;
		letter-spacing: 0.12em;
	}
	.hub-val {
		fill: var(--text);
		font-family: var(--font-mono);
		font-size: 16px;
		font-weight: 700;
	}
	.legend {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.legend li {
		display: flex;
		align-items: center;
		gap: 6px;
		font-family: var(--font-mono);
		font-size: 10px;
		color: var(--text-dim);
		letter-spacing: 0.04em;
	}
	.legend span {
		margin-left: auto;
		font-weight: 600;
	}
	.sw {
		width: 8px;
		height: 8px;
		display: inline-block;
		border-radius: 1px;
	}
	.sw.red {
		background: var(--red);
		box-shadow: 0 0 6px var(--red);
	}
	.sw.amber {
		background: var(--amber);
		box-shadow: 0 0 6px var(--amber);
	}
	.sw.cyan {
		background: var(--cyan);
		box-shadow: 0 0 6px var(--cyan);
	}
	.sw.green {
		background: var(--green);
		box-shadow: 0 0 6px var(--green);
	}
	@media (max-width: 700px) {
		.geo {
			grid-template-columns: 1fr;
		}
	}
</style>
