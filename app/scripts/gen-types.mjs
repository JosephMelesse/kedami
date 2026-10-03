// Generates the renderer's lesson types from the schema the server exports.
import { writeFile } from 'node:fs/promises'
import { compileFromFile } from 'json-schema-to-typescript'

const SCHEMA = '../server/schema/lesson.schema.json'
const OUTPUT = 'src/renderer/src/lesson/types.ts'

const ts = await compileFromFile(SCHEMA, {
  bannerComment:
    '/* Generated from server/schema/lesson.schema.json by `npm run gen:types`. Do not edit. */',
  additionalProperties: false,
  unreachableDefinitions: true,
  format: true
})
await writeFile(OUTPUT, ts)
console.log(`wrote ${OUTPUT}`)
