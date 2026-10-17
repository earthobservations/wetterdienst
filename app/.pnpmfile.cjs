// swagger-ui-dist depends on @scarf/scarf, an analytics package whose postinstall reports every install to
// scarf.sh. The app only serves swagger-ui-dist's files (`app/pages/docs.vue`), which do not use it, and
// `dangerouslyAllowAllBuilds` would let that script run on every `pnpm install` and image build, so the
// dependency is dropped from the package before it is resolved.
module.exports = {
  hooks: {
    readPackage(pkg) {
      if (pkg.name === 'swagger-ui-dist' && pkg.dependencies) {
        delete pkg.dependencies['@scarf/scarf']
      }
      return pkg
    },
  },
}
