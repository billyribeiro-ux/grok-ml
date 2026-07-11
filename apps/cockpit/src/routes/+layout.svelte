<script lang="ts">
	let { children } = $props();
</script>

<div class="shell">
	<header class="top">
		<div class="brand">AETHER</div>
		<div class="sub">Mission control · telemetry only · honest gaps shown</div>
	</header>
	<main>
		{@render children()}
	</main>
</div>

<style>
	:global(html, body) {
		margin: 0;
		padding: 0;
		background: #070a0f;
		color: #e8eef7;
		font-family:
			ui-sans-serif,
			system-ui,
			-apple-system,
			Segoe UI,
			Roboto,
			Helvetica,
			Arial,
			sans-serif;
	}
	.shell {
		min-height: 100vh;
		display: flex;
		flex-direction: column;
	}
	.top {
		padding: 1rem 1.25rem;
		border-bottom: 1px solid #1c2433;
		background: #0b1018;
	}
	.brand {
		font-weight: 700;
		letter-spacing: 0.14em;
		font-size: 0.95rem;
	}
	.sub {
		margin-top: 0.25rem;
		color: #8b9bb3;
		font-size: 0.8rem;
	}
	main {
		flex: 1;
		padding: 1.25rem;
		max-width: 1100px;
		width: 100%;
		margin: 0 auto;
		box-sizing: border-box;
	}
</style>
