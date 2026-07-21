import js from '../frontend/node_modules/@eslint/js/src/index.js'
import globals from '../frontend/node_modules/globals/index.js'
import tseslint from '../frontend/node_modules/typescript-eslint/dist/index.js'
import { defineConfig, globalIgnores } from '../frontend/node_modules/eslint/lib/config-api.js'

export default defineConfig([globalIgnores(['dist']), { files: ['**/*.ts'], extends: [js.configs.recommended, tseslint.configs.recommended], languageOptions: { globals: globals.browser } }])
