<script lang="ts">
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const flight = $derived(data.flight);
	const stats = $derived(flight?.stats ?? {});
	const statEntries = $derived(Object.entries(stats));
</script>

<section class="grid">
	<article class="card">
		<h2>Flight status</h2>
		{#if flight}
			<p class="ok">Telemetry loaded</p>
			<p class="meta">name: <code>{flight.name}</code></p>
			<p class="meta">source: <code>{flight.source}</code></p>
			<p class="meta">written: <code>{flight.written_at}</code></p>
			<p class="meta">path: <code>{data.pathUsed}</code></p>
			<p class="meta">symbols: <code>{flight.symbols?.join(', ')}</code></p>
		{:else}
			<p class="warn">No telemetry yet</p>
			<p class="meta">
				Run <code>python -m aether.cli engine-flight</code> then refresh.
			</p>
		{/if}
	</article>

	<article class="card">
		<h2>Scoreboard</h2>
		{#if statEntries.length}
			<table>
				<tbody>
					{#each statEntries as [k, v] (k)}
						<tr>
							<th>{k}</th>
							<td>{typeof v === 'number' ? Number(v).toPrecision(4) : v}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		{:else}
			<p class="meta">—</p>
		{/if}
	</article>

	<article class="card wide">
		<h2>Honest gaps</h2>
		<ul>
			{#each data.gaps as g (g)}
				<li>{g}</li>
			{/each}
		</ul>
		<p class="meta">
			L0: no fabricated numbers. STAND_DOWN is a successful action. Kill-switch remains human.
		</p>
	</article>
</section>

<style>
	.grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1rem;
	}
	.card {
		background: #0d1420;
		border: 1px solid #1c2433;
		border-radius: 10px;
		padding: 1rem 1.1rem;
	}
	.wide {
		grid-column: 1 / -1;
	}
	h2 {
		margin: 0 0 0.75rem;
		font-size: 0.85rem;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: #9db0cc;
		font-weight: 600;
	}
	.ok {
		color: #3dde8c;
		margin: 0 0 0.5rem;
	}
	.warn {
		color: #f0b429;
		margin: 0 0 0.5rem;
	}
	.meta {
		margin: 0.25rem 0;
		color: #a7b4c7;
		font-size: 0.9rem;
	}
	code {
		color: #d7e3f7;
		font-size: 0.85em;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.9rem;
	}
	th {
		text-align: left;
		color: #8b9bb3;
		font-weight: 500;
		padding: 0.3rem 0.4rem 0.3rem 0;
	}
	td {
		text-align: right;
		padding: 0.3rem 0;
		font-variant-numeric: tabular-nums;
	}
	ul {
		margin: 0;
		padding-left: 1.1rem;
		color: #c5d0e0;
	}
	li {
		margin: 0.35rem 0;
	}
	@media (max-width: 800px) {
		.grid {
			grid-template-columns: 1fr;
		}
	}
</style>
