<script setup>
import { ref } from 'vue'

defineProps({
  nr: { type: String, default: '' },
  mat: { type: String, default: '' },
  anz: { type: String, default: '' },
  embedded: { type: Boolean, default: false },
})

const emit = defineEmits(['update'])

const editing = ref(null)
const draft = ref('')

const VARIES = '<varies>'

function display(value) {
  if (value === VARIES) return VARIES
  return String(value ?? '').trim() || '—'
}

function missing(value) {
  if (value === VARIES) return false
  return !String(value ?? '').trim()
}

function startEdit(field, value) {
  editing.value = field
  draft.value = value === VARIES ? '' : String(value ?? '').trim()
}

function commit(field) {
  if (editing.value !== field) return
  emit('update', field, draft.value.trim())
  editing.value = null
}
</script>

<template>
  <div class="part-metadata-panel" :class="{ embedded }" @click.stop @pointerdown.stop>
    <table class="part-metadata-table">
      <tbody>
        <tr>
          <th class="part-metadata-label" scope="row">Name</th>
          <td
            class="part-metadata-value"
            :class="{ missing: missing(nr), editable: editing !== 'nr' }"
          >
            <input
              v-if="editing === 'nr'"
              v-model="draft"
              class="part-metadata-input"
              @blur="commit('nr')"
              @keydown.enter="commit('nr')"
            />
            <span
              v-else
              class="part-metadata-value-text"
              @click="startEdit('nr', nr)"
            >{{ display(nr) }}</span>
          </td>
        </tr>
        <tr>
          <th class="part-metadata-label" scope="row">Material</th>
          <td
            class="part-metadata-value"
            :class="{ missing: missing(mat), editable: editing !== 'mat' }"
          >
            <input
              v-if="editing === 'mat'"
              v-model="draft"
              class="part-metadata-input"
              @blur="commit('mat')"
              @keydown.enter="commit('mat')"
            />
            <span
              v-else
              class="part-metadata-value-text"
              @click="startEdit('mat', mat)"
            >{{ display(mat) }}</span>
          </td>
        </tr>
        <tr>
          <th class="part-metadata-label" scope="row">Amount</th>
          <td
            class="part-metadata-value"
            :class="{ missing: missing(anz), editable: editing !== 'anz' }"
          >
            <input
              v-if="editing === 'anz'"
              v-model="draft"
              class="part-metadata-input"
              @blur="commit('anz')"
              @keydown.enter="commit('anz')"
            />
            <span
              v-else
              class="part-metadata-value-text"
              @click="startEdit('anz', anz)"
            >{{ display(anz) }}</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.part-metadata-panel {
  position: absolute;
  z-index: 2;
  transform: translate(8px, 8px);
  min-width: 10rem;
  font-size: 0.8rem;
  color: var(--color-text-summary);
  background: var(--color-surface);
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
  pointer-events: auto;
  overflow: hidden;
}

.part-metadata-panel.embedded {
  position: static;
  transform: none;
  min-width: 0;
  box-shadow: none;
  border-radius: 0;
}

.part-metadata-table {
  width: 100%;
  border-collapse: collapse;
  border: 1px solid var(--color-border);
}

.part-metadata-table th,
.part-metadata-table td {
  border: 1px solid var(--color-border);
  padding: 0.25rem 0.4rem;
  text-align: left;
  vertical-align: middle;
}

.part-metadata-label {
  font-weight: 600;
  white-space: nowrap;
  background: var(--color-surface);
}

.part-metadata-value {
  width: 100%;
  word-break: break-word;
  padding: 0;
}

.part-metadata-value.editable {
  cursor: pointer;
}

.part-metadata-value-text {
  display: block;
  padding: 0.25rem 0.4rem;
}

.part-metadata-value.missing .part-metadata-value-text {
  color: var(--color-warning-emphasis);
  background: var(--color-warning-bg);
}

.part-metadata-value.editable:hover .part-metadata-value-text {
  background-color: var(--color-neutral-selected);
  color: var(--color-text-summary);
}

.part-metadata-input {
  display: block;
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  padding: 0.25rem 0.4rem;
  font: inherit;
  color: inherit;
  border: none;
  border-radius: 0;
  background: transparent;
  outline: none;
}
</style>
