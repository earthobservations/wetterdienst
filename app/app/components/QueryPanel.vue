<script setup lang="ts">
import type { Value } from '#shared/types/api'
import { plainRows } from '~/utils/arrow-rows'
import { validateColumns, validateQuery } from '~/utils/query-validator'

const props = defineProps<{
  data: Value[]
  expectedColumns: string[]
  mode: 'station' | 'interpolation' | 'summary'
}>()

const emit = defineEmits<{
  dataTransformed: [results: Value[]]
}>()

const { t } = useI18n()

// Translate a validator result (errorKey/warningKey/messageKey + params) to text.
function valText(key: string | undefined, params?: Record<string, string>): string {
  return key ? t(key, params ?? {}) : ''
}

// Track if we're in query mode
const isQueryMode = ref(false)

// Query state
const query = ref(`SELECT * FROM data LIMIT 100`)
const queryResults = ref<Value[]>([])
const isExecuting = ref(false)
const error = ref<string | null>(null)
const warning = ref<string | null>(null)
const columnValidationMessage = ref<string | null>(null)
const syntaxError = ref<string | null>(null)
const isValidating = ref(false)

// Required columns based on mode
const requiredColumns = computed(() => {
  const base = ['station_id', 'resolution', 'dataset', 'parameter', 'timestamp', 'value', 'quality']
  if (props.mode === 'summary') {
    return [...base, 'taken_station_id']
  }
  if (props.mode === 'interpolation') {
    return [...base, 'taken_station_ids']
  }
  return base
})

// Example queries based on mode
const exampleQueries = computed(() => {
  const base = [
    {
      label: 'All data (limited)',
      query: 'SELECT * FROM data LIMIT 100',
    },
    {
      label: 'Filter by parameter',
      query: 'SELECT * FROM data WHERE parameter = \'temperature_air_mean_2m\' LIMIT 100',
    },
    {
      label: 'Aggregate by timestamp',
      query: 'SELECT timestamp, parameter, AVG(value) as avg_value FROM data GROUP BY timestamp, parameter ORDER BY timestamp LIMIT 100',
    },
    {
      label: 'Filter by value range',
      query: 'SELECT * FROM data WHERE value > 10 AND value < 30 LIMIT 100',
    },
    {
      label: 'Recent data only',
      query: 'SELECT * FROM data ORDER BY timestamp DESC LIMIT 100',
    },
  ]

  // Add mode-specific queries
  if (props.mode === 'interpolation') {
    base.push({
      label: 'Group by source stations',
      query: 'SELECT taken_station_ids, parameter, COUNT(*) as count, AVG(value) as avg_value FROM data GROUP BY taken_station_ids, parameter LIMIT 100',
    })
  }
  else if (props.mode === 'summary') {
    base.push({
      label: 'Group by source station',
      query: 'SELECT taken_station_id, parameter, COUNT(*) as count, AVG(value) as avg_value FROM data GROUP BY taken_station_id, parameter LIMIT 100',
    })
  }

  return base
})

// DuckDB instance
let db: any = null
let conn: any = null
// DuckDB's start, which a run and the syntax check share rather than start a database each
let started: Promise<void> | null = null
// the panel is gone, and a syntax check under way stops
let unmounted = false

// Initialize DuckDB
function initDuckDB(): Promise<void> {
  started ??= startDuckDB()
  return started
}

async function startDuckDB() {
  let database: any = null
  try {
    const duckdb = await import('@duckdb/duckdb-wasm')

    const JSDELIVR_BUNDLES = duckdb.getJsDelivrBundles()

    // Select a bundle based on browser checks
    const bundle = await duckdb.selectBundle(JSDELIVR_BUNDLES)

    const worker_url = URL.createObjectURL(
      new Blob([`importScripts("${bundle.mainWorker!}");`], { type: 'text/javascript' }),
    )

    // Instantiate the asynchronous version of DuckDB-wasm
    const worker = new Worker(worker_url)
    const logger = new duckdb.ConsoleLogger()
    database = new duckdb.AsyncDuckDB(logger, worker)
    await database.instantiate(bundle.mainModule, bundle.pthreadWorker)
    URL.revokeObjectURL(worker_url)

    conn = await database.connect()
    db = database
  }
  catch (err: any) {
    // told by the run that waits for it, not by one left behind or the syntax check
    console.error('Failed to initialize DuckDB:', err)
    // the next run starts it again, without the database that failed
    started = null
    database?.terminate().catch(() => {})
  }
}

// Load rows into DuckDB's `data` table
async function loadDataIntoDB(rows: Value[]) {
  // Drop table if exists
  await conn.query('DROP TABLE IF EXISTS data')

  // Create table based on first row structure
  const firstRow = rows[0]!
  const columns = Object.keys(firstRow)
  const columnDefs = columns.map((col) => {
    const value = firstRow[col as keyof typeof firstRow]
    const type = typeof value === 'number' ? 'DOUBLE' : 'VARCHAR'
    return `"${col}" ${type}`
  }).join(', ')

  await conn.query(`CREATE TABLE data (${columnDefs})`)

  // Insert data in batches to avoid query size limits
  const batchSize = 100
  for (let i = 0; i < rows.length; i += batchSize) {
    const batch = rows.slice(i, i + batchSize)
    const values = batch.map((row) => {
      const vals = columns.map((col) => {
        const value = row[col as keyof typeof row]
        if (value === null || value === undefined)
          return 'NULL'
        if (typeof value === 'number')
          return value
        // Escape single quotes in strings
        return `'${String(value).replace(/'/g, '\'\'')}'`
      }).join(', ')
      return `(${vals})`
    }).join(', ')

    await conn.query(`INSERT INTO data VALUES ${values}`)
  }
}

// The load of the panel's rows into the table, which a run and the syntax check await rather than
// load it each, their statements interleaved. A load of newer rows starts once the one before it
// has ended, and a load that failed is tried again by whoever asks next
let tableLoad: { rows: Value[], done: Promise<void> } | null = null

function loadTable(rows: Value[]): Promise<void> {
  if (tableLoad?.rows !== rows) {
    const before = tableLoad?.done.catch(() => {}) ?? Promise.resolve()
    const load = { rows, done: before.then(() => loadDataIntoDB(rows)) }
    load.done.catch(() => {
      if (tableLoad === load)
        tableLoad = null
    })
    tableLoad = load
  }
  return tableLoad.done
}

// Validate query syntax using DuckDB EXPLAIN
async function validateQuerySyntax() {
  syntaxError.value = null

  // Skip validation for empty queries
  if (!query.value.trim()) {
    return
  }

  // Basic validation first (fast)
  const validation = validateQuery(query.value)
  if (!validation.valid) {
    syntaxError.value = valText(validation.errorKey, validation.params)
    return
  }

  // Initialize DuckDB if needed (for EXPLAIN)
  await initDuckDB()
  // gone while DuckDB started: the check would load a table into a database being closed
  if (unmounted)
    return
  if (!db || !conn) {
    // Can't validate syntax without DuckDB, but don't show error
    return
  }

  isValidating.value = true

  try {
    // Use EXPLAIN to validate query syntax without executing
    // We need to have the data table ready for proper validation
    if (props.data.length > 0) {
      // the table a run may be loading already; a load that fails is told by the run
      try {
        await loadTable(props.data)
      }
      catch {
        return
      }
    }

    // Try to explain the query - this validates syntax
    await conn.query(`EXPLAIN ${query.value}`)

    // Validate output columns by running query with LIMIT 0
    // This returns schema without fetching data - very fast!
    try {
      const schemaQuery = `SELECT * FROM (${query.value}) LIMIT 0`
      const schemaResult = await conn.query(schemaQuery)
      const resultColumns = schemaResult.schema.fields.map((field: any) => field.name)

      // Validate columns using existing validator
      const columnValidation = validateColumns(resultColumns, requiredColumns.value)

      if (!columnValidation.valid) {
        syntaxError.value = valText(columnValidation.messageKey, columnValidation.params)
        return
      }
    }
    catch (err: any) {
      // If column validation fails, show error
      syntaxError.value = `Column validation error: ${err.message}`
      return
    }

    // If we get here, syntax and columns are valid
    syntaxError.value = null
  }
  catch (err: any) {
    // Extract meaningful error message
    const message = err.message || 'Syntax error'
    syntaxError.value = message
  }
  finally {
    isValidating.value = false
  }
}

// Debounced validation
let validationTimeout: NodeJS.Timeout | null = null
function debouncedValidation() {
  if (validationTimeout) {
    clearTimeout(validationTimeout)
  }
  validationTimeout = setTimeout(() => {
    validateQuerySyntax()
  }, 500) // Wait 500ms after user stops typing
}

// Watch query changes for real-time validation
watch(query, () => {
  debouncedValidation()
})

// The run the panel waits for. Leaving query mode moves it on, and a run that is no longer it
// changes nothing: no result handed on, no error, no spinner stopped under a newer run
let currentRun = 0

// Execute query
async function executeQuery() {
  // the rows the query runs on, which a Fetch can replace before it answers
  const rows = props.data
  // the query as it was validated, which can be edited while DuckDB starts or the table loads
  const sql = query.value
  error.value = null
  warning.value = null
  columnValidationMessage.value = null

  // Validate query
  const validation = validateQuery(sql)
  if (!validation.valid) {
    error.value = valText(validation.errorKey, validation.params)
    return
  }

  if (validation.warningKey) {
    warning.value = valText(validation.warningKey, validation.params)
  }

  // running from here, so Run Query cannot start a second run while DuckDB starts or the table loads
  const run = ++currentRun
  isExecuting.value = true

  try {
    // Initialize DuckDB if needed
    await initDuckDB()
    if (run !== currentRun)
      return
    if (!db || !conn) {
      error.value = 'Failed to initialize database'
      return
    }

    if (rows.length === 0) {
      error.value = 'No data available to query'
      return
    }

    try {
      await loadTable(rows)
    }
    catch (err: any) {
      if (run === currentRun) {
        console.error('Failed to load data into DuckDB:', err)
        error.value = `Failed to load data: ${err.message || 'Unknown error'}`
      }
      return
    }

    const result = await conn.query(sql)
    // each value made plain by its column's type, as the REST API would answer it, where Arrow's own
    // toJSON() left BigInts, milliseconds since the epoch and its own nested rows (GH-2068, GH-2071).
    // Typed as values, as the panel has always handed its rows on; validateColumns checks below that
    // they carry the columns a value needs
    const resultArray = plainRows(result) as unknown as Value[]

    // left by Cancel, or by a Fetch whose newer rows the result would replace
    if (run !== currentRun)
      return

    // Validate columns
    if (resultArray.length > 0) {
      const resultColumns = Object.keys(resultArray[0]!)
      const columnValidation = validateColumns(resultColumns, requiredColumns.value)

      if (!columnValidation.valid) {
        error.value = valText(columnValidation.messageKey, columnValidation.params)
        return
      }

      if (columnValidation.messageKey) {
        columnValidationMessage.value = valText(columnValidation.messageKey, columnValidation.params)
      }
    }

    queryResults.value = resultArray
    emit('dataTransformed', resultArray)
  }
  catch (err: any) {
    if (run === currentRun) {
      console.error('Query execution error:', err)
      error.value = `Query error: ${err.message}`
    }
  }
  finally {
    // a newer run's spinner is its own
    if (run === currentRun)
      isExecuting.value = false
  }
}

// Load example query
function loadExample(exampleQuery: string) {
  query.value = exampleQuery
}

// Toggle query mode
function enableQueryMode() {
  isQueryMode.value = true
}

function disableQueryMode() {
  // the run under way is left: it hands on no result, and tells no error, when it answers
  currentRun++
  isExecuting.value = false
  isQueryMode.value = false
  queryResults.value = []
  error.value = null
  warning.value = null
  columnValidationMessage.value = null
  emit('dataTransformed', props.data) // Reset to original data
}

// Watch for data changes - reset query mode
watch(() => props.data, () => {
  if (isQueryMode.value) {
    disableQueryMode()
  }
}, { deep: true })

// Cleanup on unmount
onUnmounted(async () => {
  unmounted = true
  // the delayed syntax check would start a database that nothing ends
  if (validationTimeout)
    clearTimeout(validationTimeout)
  // a start under way ends before the database it makes can be
  await started
  if (conn) {
    await conn.close()
    conn = null
  }
  if (db) {
    await db.terminate()
    db = null
  }
})
</script>

<template>
  <div class="w-full">
    <div v-if="!isQueryMode" class="mb-4">
      <UButton
        label="Transform with SQL Query"
        icon="i-lucide-database"
        color="neutral"
        variant="soft"
        size="sm"
        block
        @click="enableQueryMode"
      />
    </div>

    <UCard v-else class="mb-4">
      <template #header>
        <div class="flex items-center justify-between">
          <h3 class="text-lg font-bold">
            SQL Query Transform
          </h3>
          <div class="flex gap-2">
            <UButton
              label="Run Query"
              icon="i-heroicons-play"
              color="primary"
              size="sm"
              :disabled="isExecuting || !query.trim() || !!syntaxError"
              :loading="isExecuting"
              @click="executeQuery"
            />
            <UButton
              label="Cancel"
              icon="i-heroicons-x-mark"
              color="neutral"
              variant="ghost"
              size="sm"
              @click="disableQueryMode"
            />
          </div>
        </div>
      </template>

      <div class="space-y-4">
        <!-- Query Editor -->
        <div class="space-y-2">
          <div class="relative">
            <UTextarea
              v-model="query"
              :rows="6"
              placeholder="Enter your SQL query here..."
              class="font-mono text-sm w-full"
              :class="syntaxError ? 'border-red-500 dark:border-red-400' : ''"
            />
            <div v-if="isValidating" class="absolute top-2 right-2">
              <UIcon name="i-heroicons-arrow-path" class="animate-spin text-gray-400" />
            </div>
          </div>

          <!-- Syntax validation feedback -->
          <UAlert
            v-if="syntaxError"
            color="error"
            variant="soft"
            icon="i-heroicons-exclamation-triangle"
            title="Syntax Error"
            :description="syntaxError"
          />

          <div class="text-xs text-gray-500">
            Query the <code class="px-1 py-0.5 bg-gray-100 dark:bg-gray-800 rounded">data</code> table with standard SQL.
            <div>Required columns: <code class="px-1 py-0.5 bg-gray-100 dark:bg-gray-800 rounded">{{ requiredColumns.join(', ') }}</code></div>
            <div class="text-gray-400">
              Available columns: <code class="px-1 py-0.5 bg-gray-100 dark:bg-gray-800 rounded">{{ expectedColumns.join(', ') }}</code>
            </div>
          </div>
        </div>

        <!-- Example Queries -->
        <details class="text-sm">
          <summary class="cursor-pointer font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100">
            Example Queries
          </summary>
          <div class="mt-2 flex flex-wrap gap-2">
            <UButton
              v-for="example in exampleQueries"
              :key="example.label"
              :label="example.label"
              size="xs"
              color="neutral"
              variant="soft"
              @click="loadExample(example.query)"
            />
          </div>
        </details>

        <!-- Error Message -->
        <UAlert
          v-if="error"
          icon="i-heroicons-exclamation-triangle"
          color="error"
          variant="soft"
          :title="error"
          :close-button="{ icon: 'i-heroicons-x-mark-20-solid', color: 'neutral', variant: 'link' }"
          @close="error = null"
        />

        <!-- Warning Message -->
        <UAlert
          v-if="warning"
          icon="i-heroicons-exclamation-circle"
          color="warning"
          variant="soft"
          :title="warning"
          :close-button="{ icon: 'i-heroicons-x-mark-20-solid', color: 'neutral', variant: 'link' }"
          @close="warning = null"
        />

        <!-- Column Validation Message -->
        <UAlert
          v-if="columnValidationMessage"
          icon="i-heroicons-information-circle"
          color="info"
          variant="soft"
          :title="columnValidationMessage"
          :close-button="{ icon: 'i-heroicons-x-mark-20-solid', color: 'neutral', variant: 'link' }"
          @close="columnValidationMessage = null"
        />

        <!-- Results Info -->
        <div v-if="queryResults.length > 0" class="text-sm font-medium text-green-600 dark:text-green-400">
          ✓ Query executed successfully: {{ queryResults.length }} row(s) returned
        </div>
      </div>
    </UCard>
  </div>
</template>
