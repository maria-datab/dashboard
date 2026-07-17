<template>
  <div class="home">
    <h1 class="home-title">Dashboard</h1>
    <p class="home-subtitle">Select a tool to get started.</p>
    <div class="tool-grid">
      <router-link to="/boxout" class="tool-card">
        <strong>DoorBoxOut</strong>
        <p>Parametric box design via CSV or chat. 3D viewer + nesting.</p>
      </router-link>
      <router-link to="/simple-parts" class="tool-card">
        <strong>Simple Parts</strong>
        <p>DXF part processing, metadata correction, nesting, and CNC export.</p>
      </router-link>
    </div>
  </div>
</template>

<style scoped>
.home {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 1.5rem;
  padding: 2rem;
  background: var(--color-neutral-bg);
}

.home-title {
  margin: 0;
  font-size: 1.5rem;
  color: var(--color-text-summary);
}

.home-subtitle {
  margin: 0;
  color: var(--color-text-muted);
  font-size: 0.9rem;
}

.tool-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1rem;
  width: 100%;
  max-width: 600px;
}

.tool-card {
  display: block;
  padding: 1.25rem 1.5rem;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
  text-decoration: none;
  color: var(--color-text-summary);
  transition: border-color 0.15s, box-shadow 0.15s;
}

.tool-card:hover {
  border-color: var(--color-accent);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.tool-card strong {
  display: block;
  font-size: 1rem;
  margin-bottom: 0.4rem;
  color: var(--color-accent);
}

.tool-card p {
  margin: 0;
  font-size: 0.82rem;
  line-height: 1.4;
  color: var(--color-text-muted);
}
</style>
