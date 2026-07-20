<script setup>
import { useRoute } from 'vue-router'

const route = useRoute()
</script>

<template>
  <div class="dashboard-root">
    <nav class="top-nav" aria-label="Main">
      <span class="top-nav-logo">Dashboard</span>
      <router-link to="/" class="nav-link" :class="{ 'router-link-active': route.path === '/' }">
        Home
      </router-link>
      <router-link to="/boxout" class="nav-link">DoorBoxOut</router-link>
      <router-link to="/simple-parts" class="nav-link">Simple Parts</router-link>
    </nav>
    <router-view class="dashboard-view" :key="route.fullPath" />
  </div>
</template>

<style>
.dashboard-root {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  background: var(--color-neutral-bg);
}

.top-nav {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0 1rem;
  height: 36px;
  background: var(--color-accent);
  color: #fff;
  font-size: 0.82rem;
  z-index: 100;
}

.top-nav-logo {
  font-weight: 700;
  letter-spacing: -0.01em;
  margin-right: auto;
}

.nav-link {
  color: rgba(255, 255, 255, 0.85);
  text-decoration: none;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  transition: background 0.12s;
}

.nav-link:hover,
.nav-link.router-link-active {
  background: rgba(255, 255, 255, 0.18);
  color: #fff;
}

.dashboard-view {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* Tool apps use 100vh when standalone; fill the shell pane when embedded. */
.dashboard-view .app {
  height: 100%;
}
</style>
