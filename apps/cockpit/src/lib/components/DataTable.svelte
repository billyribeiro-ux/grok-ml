<script lang="ts">
	type Col = {
		key: string;
		label: string;
		align?: 'left' | 'right';
		tone?: (row: Record<string, unknown>) => string;
		fmt?: (v: unknown, row: Record<string, unknown>) => string;
	};

	type Props = {
		columns: Col[];
		rows: Record<string, unknown>[];
		maxHeight?: string;
		empty?: string;
	};

	let {
		columns,
		rows,
		maxHeight = '280px',
		empty = 'NO ROWS'
	}: Props = $props();
</script>

{#if !rows.length}
	<p class="empty mono">{empty}</p>
{:else}
	<div class="scroll" style:max-height={maxHeight}>
		<table>
			<thead>
				<tr>
					{#each columns as c (c.key)}
						<th class={c.align === 'right' ? 'r' : ''}>{c.label}</th>
					{/each}
				</tr>
			</thead>
			<tbody>
				{#each rows as row, i (i)}
					<tr>
						{#each columns as c (c.key)}
							{@const raw = row[c.key]}
							{@const tone = c.tone?.(row) ?? ''}
							<td class="mono {c.align === 'right' ? 'r' : ''} {tone}">
								{c.fmt ? c.fmt(raw, row) : raw == null ? '—' : String(raw)}
							</td>
						{/each}
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
{/if}

<style>
	.scroll {
		overflow: auto;
		border: 1px solid var(--border);
		background: #080c14;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 10px;
	}
	th {
		position: sticky;
		top: 0;
		background: #0f1520;
		text-align: left;
		font-family: var(--font-mono);
		font-size: 9px;
		letter-spacing: 0.1em;
		color: var(--text-mute);
		padding: 5px 6px;
		border-bottom: 1px solid var(--border);
		z-index: 1;
	}
	th.r,
	td.r {
		text-align: right;
	}
	td {
		padding: 4px 6px;
		border-bottom: 1px solid rgba(255, 255, 255, 0.03);
		color: var(--text-dim);
		white-space: nowrap;
	}
	tr:hover td {
		background: rgba(255, 176, 32, 0.04);
		color: var(--text);
	}
	.empty {
		color: var(--amber);
		font-size: 11px;
		letter-spacing: 0.08em;
		padding: 12px 4px;
	}
</style>
