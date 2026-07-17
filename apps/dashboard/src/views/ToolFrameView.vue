<script setup>
import { computed } from 'vue'

const props = defineProps({
  title: { type: String, required: true },
  originEnvKey: { type: String, required: true },
  defaultOrigin: { type: String, required: true },
})

const iframeSrc = computed(() => {
  const fromEnv = import.meta.env[props.originEnvKey]
  if (typeof fromEnv === 'string' && fromEnv.trim()) return fromEnv.trim()
  return props.defaultOrigin
})
</script>

<template>
  <div class="tool-frame">
    <iframe
      class="tool-frame__iframe"
      :src="iframeSrc"
      :title="title"
      allow="clipboard-read; clipboard-write"
    />
  </div>
</template>

<style scoped>
.tool-frame {
  height: 100%;
  min-height: 0;
  background: var(--color-viewer-background);
}

.tool-frame__iframe {
  display: block;
  width: 100%;
  height: 100%;
  border: 0;
  background: var(--color-surface);
}
</style>
