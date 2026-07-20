/**
 * Load rhino3dm WASM once (singleton) for all tool apps.
 */
import rhino3dm from 'rhino3dm/rhino3dm.module.js'
import rhino3dmWasm from 'rhino3dm/rhino3dm.wasm?url'

let rhino = null
let loadPromise = null

/** @returns {Promise<object>} rhino3dm module */
export async function loadRhino() {
  if (rhino) return rhino
  if (loadPromise) return loadPromise

  loadPromise = rhino3dm({ locateFile: () => rhino3dmWasm }).then((m) => {
    rhino = m
    return m
  })

  return loadPromise
}
