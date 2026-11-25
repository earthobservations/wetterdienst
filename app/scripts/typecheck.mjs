// `pnpm typecheck`: the app is checked twice, and fails if either check does (GH-4342).
//
//   1. `nuxt typecheck` (vue-tsc, on TypeScript 6.0.3: .pnpmfile.cjs) checks the `.vue` files, templates
//      included, and the `.ts` code they use. It also writes Nuxt's tsconfigs into .nuxt/, which the
//      second check extends.
//   2. `tsc` 7 (the app's TypeScript) checks the `.ts` code, through typecheck/<project>.json: one
//      per tsconfig Nuxt generates, and `tests`, which Nuxt has no project for (the unit and e2e tests,
//      their helpers and setup, and playwright.config.ts; GH-4360). TypeScript 7 cannot read a `.vue`
//      file: typecheck/vue-shim.d.ts gives the imports of one a loose type, and the first check is the
//      one that holds them to theirs.
//
// Both always run, so one failure does not hide the other's errors. Drop the first check, and the
// shim, once a Vue type checker runs on TypeScript 7 (#4343).
import { spawn } from 'node:child_process'
import process from 'node:process'

const PROJECTS = ['app', 'server', 'shared', 'node', 'tests']

function run(command, args) {
  return new Promise((resolve) => {
    // one command line, so that Windows finds the `.cmd` of a bin (Node warns about arguments next to `shell`)
    const child = spawn([command, ...args].join(' '), { shell: true, stdio: ['ignore', 'pipe', 'pipe'] })
    let output = ''
    child.stdout.on('data', chunk => (output += chunk))
    child.stderr.on('data', chunk => (output += chunk))
    child.on('close', code => resolve({ code: code ?? 1, output }))
  })
}

function report(title, result) {
  console.log(`\n== ${title}: ${result.code === 0 ? 'passed' : 'FAILED'}`)
  if (result.output.trim()) {
    console.log(result.output.trimEnd())
  }
}

const vue = await run('nuxt', ['typecheck'])
report('vue-tsc (.vue files and the .ts they use, TypeScript 6.0.3)', vue)

const results = await Promise.all(PROJECTS.map(project => run('tsc', ['-p', `typecheck/${project}.json`])))
let failed = vue.code !== 0
for (const [index, result] of results.entries()) {
  report(`tsc 7 (.ts code, ${PROJECTS[index]} project)`, result)
  failed ||= result.code !== 0
}

process.exit(failed ? 1 : 0)
