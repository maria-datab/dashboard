import { is3dDxf, dxfTextHasAcisSolid } from '../../dxfDetection.js'

/**
 * True for plain 2D DXF uploads — route through Hops geometryMode=0 (same as DWG).
 *
 * @param {object} options
 * @param {'dxf' | 'dwg' | '3dm'} options.sourceType
 * @param {object | null | undefined} [options.parsedDxf]
 * @param {string | null | undefined} [options.dxfText]
 */
export function isPlain2dDxf({ sourceType, parsedDxf, dxfText }) {
  if (sourceType !== 'dxf') return false
  if (parsedDxf && is3dDxf(parsedDxf)) return false
  if (dxfTextHasAcisSolid(dxfText)) return false
  return true
}

/**
 * Hops input: 0 = 2D pipeline, 1 = 3D pipeline. Call before every /api/hops/solve.
 *
 * @param {object} options
 * @param {'dxf' | 'dwg' | '3dm'} options.sourceType
 * @param {'2d' | '3d' | null | undefined} [options.geometryMode]
 * @param {object | null | undefined} [options.parsedDxf]
 * @param {string | null | undefined} [options.dxfText]
 * @returns {0 | 1}
 */
export function resolveHopsGeometryModeInt({
  sourceType,
  geometryMode,
  parsedDxf,
  dxfText,
}) {
  if (geometryMode === '2d') return 0
  if (geometryMode === '3d') return 1
  if (sourceType === '3dm') return 1
  if (sourceType === 'dwg') return 0
  if (sourceType === 'dxf' && parsedDxf && is3dDxf(parsedDxf)) return 1
  if (sourceType === 'dxf' && dxfTextHasAcisSolid(dxfText)) return 1
  return 0
}

/**
 * Classify uploaded input as flat GH pipeline ('2d') or solid GH pipeline ('3d').
 * When hopsGeometryMode is known (after a Hops call), it is authoritative.
 *
 * @param {object} options
 * @param {0 | 1 | null | undefined} [options.hopsGeometryMode]
 * @param {'dxf' | 'dwg' | '3dm'} options.sourceType
 * @param {object | null | undefined} [options.parsedDxf]
 * @param {string | null | undefined} [options.dxfText]
 * @returns {'2d' | '3d'}
 */
export function resolveGeometryMode({
  hopsGeometryMode,
  sourceType,
  parsedDxf,
  dxfText,
}) {
  if (hopsGeometryMode === 0) return '2d'
  if (hopsGeometryMode === 1) return '3d'
  if (sourceType === '3dm') return '3d'
  if (sourceType === 'dxf' && parsedDxf && is3dDxf(parsedDxf)) return '3d'
  if (sourceType === 'dxf' && dxfTextHasAcisSolid(dxfText)) return '3d'
  if (sourceType === 'dwg') return '2d'
  return '2d'
}
