<script setup>
import { ref, watch } from 'vue'
import { DXFViewer as DxfViewer } from 'dxf-vuer'
import * as THREE from 'three'

const props = defineProps({
  dxf: { type: Object, required: true },
  cameraStateToRestore: { type: Object, default: null },
  hiddenLayers: { type: Array, default: () => [] },
  showLayerPanel: { type: Boolean, default: false },
  highlightColor: { type: Number, required: true },
  selectedHandles: { type: Array, default: () => [] },
  highlightSafeHandles: { type: Function, required: true },
  pickingEnabled: { type: Boolean, default: true },
})

const emit = defineEmits(['update:hiddenLayers', 'ready', 'entity-click'])

const viewerRef = ref(null)
let controlsChangeHandler = null

function getCamera() {
  return viewerRef.value?.getCamera?.() ?? null
}

function getCanvas() {
  return viewerRef.value?.getRenderer?.()?.domElement ?? null
}

function getOriginOffset() {
  return viewerRef.value?.getOriginOffset?.() ?? { x: 0, y: 0, z: 0 }
}

function captureCameraState() {
  const camera = getCamera()
  const controls = viewerRef.value?.getControls?.()
  if (!camera || !controls) return null
  const origin = getOriginOffset()
  return {
    zoom: camera.zoom,
    worldTargetX: controls.target.x + origin.x,
    worldTargetY: controls.target.y + origin.y,
  }
}

function restoreCameraState(state) {
  const camera = getCamera()
  const controls = viewerRef.value?.getControls?.()
  if (!camera || !controls || !state) return
  const origin = getOriginOffset()
  camera.zoom = state.zoom
  controls.target.x = state.worldTargetX - origin.x
  controls.target.y = state.worldTargetY - origin.y
  camera.position.x = controls.target.x
  camera.position.y = controls.target.y
  camera.updateProjectionMatrix()
  controls.update()
}

function applyHighlight(handles) {
  const viewer = viewerRef.value
  if (!viewer) return
  const dxfHandles = props.highlightSafeHandles(handles)
  if (dxfHandles.length) viewer.highlight(dxfHandles)
  else viewer.clearHighlight()
}

function clearHighlight() {
  viewerRef.value?.clearHighlight()
}

function zoomToEntity(handles) {
  viewerRef.value?.zoomToEntity(handles)
}

function setControlsChangeListener(fn) {
  const controls = viewerRef.value?.getControls?.()
  if (controlsChangeHandler && controls) {
    controls.removeEventListener('change', controlsChangeHandler)
  }
  controlsChangeHandler = fn ?? null
  if (fn && controls) controls.addEventListener('change', fn)
}

function onLoaded(success) {
  if (success === false) return
  const controls = viewerRef.value?.getControls?.()
  if (controls) {
    controls.mouseButtons = {
      LEFT: -1,
      MIDDLE: THREE.MOUSE.PAN,
      RIGHT: THREE.MOUSE.PAN,
    }
  }
  if (props.cameraStateToRestore) {
    restoreCameraState(props.cameraStateToRestore)
  }
  applyHighlight(props.selectedHandles)
  emit('ready')
}

watch(() => props.selectedHandles, (handles) => {
  applyHighlight(handles)
}, { deep: true })

function getControls() {
  return viewerRef.value?.getControls?.() ?? null
}

function resize() {
  viewerRef.value?.resize?.()
}

defineExpose({
  getContainerEl: () => viewerRef.value?.$el ?? null,
  getCamera,
  getControls,
  getCanvas,
  getOriginOffset,
  captureCameraState,
  restoreCameraState,
  applyHighlight,
  clearHighlight,
  zoomToEntity,
  setControlsChangeListener,
  resize,
})
</script>

<template>
  <div class="dxf-2d-viewer">
    <DxfViewer
    ref="viewerRef"
    :hidden-layers="hiddenLayers"
    :dxf-data="dxf"
    :show-layer-panel="showLayerPanel"
    :picking-enabled="pickingEnabled"
    :highlight-on-hover="false"
    :highlight-associated="false"
    :highlight-color="highlightColor"
    style="width: 100%; height: 100%"
    @dxf-loaded="onLoaded"
    @entity-click="emit('entity-click', $event)"
    @update:hidden-layers="emit('update:hiddenLayers', $event)"
  />
  </div>
</template>

<style scoped>
.dxf-2d-viewer {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  min-height: 0;
}
</style>
