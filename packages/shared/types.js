/**
 * Shared ChatMessage type used by both apps.
 *
 * @typedef {'user' | 'assistant'} ChatMessageRole
 * @typedef {'text' | 'file' | 'result' | 'error' | 'confirm'} ChatMessageKindBase
 *
 * @typedef {object} ChatMessage
 * @property {string} id
 * @property {ChatMessageRole} role
 * @property {string} kind          - ChatMessageKindBase or app-specific extension
 * @property {string} content
 * @property {Record<string, unknown>} [meta]
 */

export {}
