<script setup lang="ts">
import type { Value } from '#shared/types/api'
import { validateColumns, validateQuery } from '~/utils/query-validator'

const props = defineProps<{
  data: Value[]
  expectedColumns: string[]
  mode: 'station' | 'interpolation' | 'summary'
}>()

const emit = defineEmits<{
  dataTransformed: [results: Value[]]
}>()

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
  const base = ['station_id', 'resolution', 'dataset', 'parameter', 'date', 'value', 'quality']
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
      label: 'Aggregate by date',
      query: 'SELECT date, parameter, AVG(value) as avg_value FROM data GROUP BY date, parameter ORDER BY date LIMIT 100',
    },
    {
      label: 'Filter by value range',
      query: 'SELECT * FROM data WHERE value > 10 AND value < 30 LIMIT 100',
    },
    {
      label: 'Recent data only',
      query: 'SELECT * FROM data ORDER BY date DESC LIMIT 100',
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

// Initialize DuckDB
async function initDuckDB() {
  if (db)
    return

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
    db = new duckdb.AsyncDuckDB(logger, worker)
    await db.instantiate(bundle.mainModule, bundle.pthreadWorker)
    URL.revokeObjectURL(worker_url)

    conn = await db.connect()
  }
  catch (err: any) {
    console.error('Failed to initialize DuckDB:', err)
    error.value = `Failed to initialize DuckDB: ${err.message || 'Unknown error'}`
  }
}

// Load data into DuckDB
async function loadDataIntoDB() {
  if (!conn || !db || !props.data.length) {
    return
  }

  try {
    // Drop table if exists
    await conn.query('DROP TABLE IF EXISTS data')

    // Create table based on first row structure
    const firstRow = props.data[0]
    if (!firstRow) {
      error.value = 'No data to load'
      return
    }

    const columns = Object.keys(firstRow)
    const columnDefs = columns.map((col) => {
      const value = firstRow[col as keyof typeof firstRow]
      const type = typeof value === 'number' ? 'DOUBLE' : 'VARCHAR'
      return `"${col}" ${type}`
    }).join(', ')

    await conn.query(`CREATE TABLE data (${columnDefs})`)

    // Insert data in batches to avoid query size limits
    const batchSize = 100
    for (let i = 0; i < props.data.length; i += batchSize) {
      const batch = props.data.slice(i, i + batchSize)
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
  catch (err: any) {
    console.error('Failed to load data into DuckDB:', err)
    error.value = `Failed to load data: ${err.message || 'Unknown error'}`
  }
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
    syntaxError.value = validation.error || 'Invalid query'
    return
  }

  // Initialize DuckDB if needed (for EXPLAIN)
  await initDuckDB()
  if (!db || !conn) {
    // Can't validate syntax without DuckDB, but don't show error
    return
  }

  isValidating.value = true

  try {
    // Use EXPLAIN to validate query syntax without executing
    // We need to have the data table ready for proper validation
    if (props.data.length > 0) {
      // Ensure table exists (load just first row for validation)
      try {
        await conn.query('SELECT 1 FROM data LIMIT 1')
      }
      catch {
        // Table doesn't exist, create it with minimal data
        await loadDataIntoDB()
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
        syntaxError.value = columnValidation.message || 'Column validation failed'
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

// Execute query
async function executeQuery() {
  error.value = null
  warning.value = null
  columnValidationMessage.value = null

  // Validate query
  const validation = validateQuery(query.value)
  if (!validation.valid) {
    error.value = validation.error || 'Invalid query'
    return
  }

  if (validation.warning) {
    warning.value = validation.warning
  }

  // Initialize DuckDB if needed
  await initDuckDB()
  if (!db || !conn) {
    error.value = 'Failed to initialize database'
    return
  }

  // Load data if needed
  if (props.data.length > 0) {
    await loadDataIntoDB()
  }
  else {
    error.value = 'No data available to query'
    return
  }

  isExecuting.value = true

  try {
    const result = await conn.query(query.value)
    const resultArray = result.toArray().map((row: any) => row.toJSON())

    // Validate columns
    if (resultArray.length > 0) {
      const resultColumns = Object.keys(resultArray[0])
      const columnValidation = validateColumns(resultColumns, requiredColumns.value)

      if (!columnValidation.valid) {
        error.value = columnValidation.message || 'Column validation failed'
        return
      }

      if (columnValidation.message) {
        columnValidationMessage.value = columnValidation.message
      }
    }

    queryResults.value = resultArray
    emit('dataTransformed', resultArray)
  }
  catch (err: any) {
    console.error('Query execution error:', err)
    error.value = `Query error: ${err.message}`
  }
  finally {
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
          <h3 class="text-lg font-semibold">
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
