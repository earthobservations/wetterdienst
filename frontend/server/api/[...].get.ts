type QueryValue = string | number | boolean | undefined | null
type QueryObject = Record<string, QueryValue | QueryValue[]>

function buildSearchParams(query: QueryObject): URLSearchParams {
  const params = new URLSearchParams()
  Object.entries(query).forEach(([key, val]) => {
    if (val === undefined || val === null)
      return
    if (Array.isArray(val)) {
      val.forEach(v => params.append(key, String(v)))
    }
    else {
      params.append(key, String(val))
    }
  })
  return params
}

export default defineEventHandler(async (event): Promise<unknown> => {
  const { public: { apiBase } } = useRuntimeConfig()
  const fullPath = event.path.replace(/^\/api/, '') || '/'
  const path = fullPath.split('?')[0]
  const query = getQuery(event) as QueryObject

  const params = buildSearchParams(query)
  const queryString = params.toString()
  const url = `${apiBase}${path}${queryString ? `?${queryString}` : ''}`

  try {
    return await $fetch(url, { method: 'GET' })
  }
  catch (error: unknown) {
    // Return FastAPI-compatible error format
    const fetchError = error as { response?: { status?: number }, status?: number, data?: unknown, message?: string }
    const statusCode = fetchError?.response?.status || fetchError?.status || 500
    setResponseStatus(event, statusCode)

    // If the backend returned FastAPI error format, pass it through
    if (fetchError?.data) {
      return fetchError.data
    }

    // Otherwise, create FastAPI-compatible error response
    return {
      detail: fetchError?.message || 'An error occurred',
    } satisfies ApiErrorResponse
  }
})
