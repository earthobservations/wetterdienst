// swagger-ui-dist depends on @scarf/scarf, an analytics package whose postinstall reports every install to
// scarf.sh. The app only serves swagger-ui-dist's files (`app/pages/docs.vue`), which do not use it, and
// `allowBuilds` in pnpm-workspace.yaml would have to name it for the install to pass, so the dependency
// is dropped from the package before it is resolved.
//
// TypeScript 7 (the Go port) is the app's TypeScript, but its package exports only `.` and `./unstable/*`:
// it has no `lib/tsc` and no classic JavaScript API. A tool that loads that API gets its own copy of
// TypeScript 6.0.3 here, and only that tool (#4342). Each of them declares `typescript` as a peer
// dependency, which pnpm resolves to the app's TypeScript 7 and which neither `overrides` nor
// `packageExtensions` can redirect, so the peer is replaced by a dependency on 6.0.3. Drop each entry
// once the tool supports TypeScript 7 (#4343):
//   vue-tsc             type-checks the `.vue` files and loads `typescript/lib/tsc`; with TypeScript 7
//                       it fails at start with ERR_PACKAGE_PATH_NOT_EXPORTED: './lib/tsc'
//   openapi-typescript  (`pnpm gen:api-types`) builds the types with `ts.factory`, which TypeScript 7
//                       does not export: "Cannot read properties of undefined (reading
//                       'createKeywordTypeNode')"
//   @typescript-eslint/*, ts-api-utils, ts-declaration-location, @vitest/eslint-plugin
//                       (`pnpm lint`, through @antfu/eslint-config and @nuxt/eslint) the ESLint rules
//                       that read types; typescript-eslint refuses TypeScript 7.0 at load ("does not
//                       support TS 7.0") and supports it from 7.1 (typescript-eslint#10940)
const NEEDS_TYPESCRIPT_6 = new Set([
  'vue-tsc',
  'openapi-typescript',
  'typescript-eslint',
  'ts-api-utils',
  'ts-declaration-location',
  '@vitest/eslint-plugin',
])
const needsTypescript6 = name => NEEDS_TYPESCRIPT_6.has(name) || name.startsWith('@typescript-eslint/')

module.exports = {
  hooks: {
    readPackage(pkg) {
      if (pkg.name === 'swagger-ui-dist' && pkg.dependencies) {
        delete pkg.dependencies['@scarf/scarf']
      }
      if (needsTypescript6(pkg.name)) {
        if (pkg.peerDependencies) {
          delete pkg.peerDependencies.typescript
        }
        if (pkg.peerDependenciesMeta) {
          delete pkg.peerDependenciesMeta.typescript
        }
        pkg.dependencies = { ...pkg.dependencies, typescript: 'npm:typescript@6.0.3' }
      }
      return pkg
    },
  },
}
