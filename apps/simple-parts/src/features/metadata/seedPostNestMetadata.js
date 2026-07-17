/** GH PostInjectionNames / PostInjectionAmount — parallel to InitialPartKeys by index. */

export function normalizeGhStringList(raw) {
  if (!Array.isArray(raw)) return []
  return raw.map((value) => String(value ?? '').trim())
}

function metaFromGhIndex(names, amounts, index) {
  const nr = String(names[index] ?? '').trim()
  const anz = String(amounts[index] ?? '').trim()
  if (!nr && !anz) return null
  const out = {}
  if (nr) out.nr = nr
  if (anz) out.anz = anz
  return out
}

function mergeSeedEntry(existing, seeded) {
  if (!seeded) return existing ?? null
  if (!existing) return { ...seeded }
  return {
    nr: String(existing.nr ?? '').trim() || seeded.nr,
    mat: String(existing.mat ?? '').trim() || seeded.mat,
    anz: String(existing.anz ?? '').trim() || seeded.anz,
  }
}

function applyMetaToKeys(overrides, keys, meta) {
  if (!meta) return overrides
  let next = { ...overrides }
  for (const key of keys) {
    const id = String(key ?? '').trim()
    if (!id) continue
    const merged = mergeSeedEntry(next[id], meta)
    if (merged) next[id] = merged
  }
  return next
}

export function buildDescriptorBaseMetaFromGhLists({
  partKeys = [],
  postInjectionNames = [],
  postInjectionAmount = [],
  meshCount = 0,
} = {}) {
  const names = normalizeGhStringList(postInjectionNames)
  const amounts = normalizeGhStringList(postInjectionAmount)
  const count = Math.max(meshCount, partKeys.length, names.length, amounts.length)
  const baseMeta = []
  for (let i = 0; i < count; i += 1) {
    baseMeta[i] = metaFromGhIndex(names, amounts, i) ?? {}
  }
  return baseMeta
}

/**
 * Seed metadataOverrides and mesh descriptor base meta from GH association lists.
 * meshes[i] ↔ partKeys[i] ↔ postInjectionNames[i] ↔ postInjectionAmount[i].
 */
export function seedPostNestMetadata({
  partKeys = [],
  postInjectionNames = [],
  postInjectionAmount = [],
  metadataOverrides = {},
  meshCount = 0,
} = {}) {
  const names = normalizeGhStringList(postInjectionNames)
  const amounts = normalizeGhStringList(postInjectionAmount)
  let overrides = { ...metadataOverrides }
  const meshDescriptorBaseMeta = buildDescriptorBaseMetaFromGhLists({
    partKeys,
    postInjectionNames: names,
    postInjectionAmount: amounts,
    meshCount,
  })

  for (let i = 0; i < meshCount; i += 1) {
    const meta = metaFromGhIndex(names, amounts, i)
    if (!meta) continue
    const partKey = String(partKeys[i] ?? '').trim()
    const canonicalKey = partKey || `mesh:${i}`
    overrides = applyMetaToKeys(overrides, [canonicalKey], meta)
  }

  return { metadataOverrides: overrides, meshDescriptorBaseMeta }
}
