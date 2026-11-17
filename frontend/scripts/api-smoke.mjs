import { normalizePage } from '../src/api/utils.js'

console.assert(normalizePage(undefined).size === 10, 'default size')
console.assert(normalizePage({ size: 999 }).size === 100, 'size cap')
console.assert(normalizePage({ page: 0 }).page === 1, 'page floor')
console.log('api smoke ok')
