<script setup>
/**
 * Generic sidebar shell. Render the app title + pass a ChatPanel as the default slot.
 *
 * Usage:
 *   <Sidebar title="DoorBoxOut">
 *     <ChatPanel ... />
 *   </Sidebar>
 */
defineProps({
  title: { type: String, required: true },
})
</script>

<template>
  <aside class="sidebar">
    <h1 class="sidebar-title">{{ title }}</h1>
    <slot />
  </aside>
</template>

<style scoped>
/* .sidebar layout rules live in tokens.css; only decorative rules here */
.sidebar-title {
  margin: 0 0 0.25rem;
  font-size: 1rem;
  font-weight: 700;
  color: var(--color-text-summary);
  letter-spacing: -0.01em;
}
</style>
