import type { ApiErrorResponse } from '#types/api.types'
import type { H3Event } from 'h3'

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

async function handleImageResponse(
  event: H3Event,
  url: string,
  format: 'png' | 'svg',
): Promise<Uint8Array | string | ApiErrorResponse> {
  try {
    const response = await fetch(url, { method: 'GET' })

    if (format === 'png') {
      setResponseHeader(event, 'content-type', 'image/png')
      const arrayBuffer = await response.arrayBuffer()
      const bytes = new Uint8Array(arrayBuffer)
      await send(event, bytes, 'image/png')
      return bytes
    }

    // SVG
    const svgText = await response.text()
    await send(event, svgText, 'image/svg+xml')
    return svgText
  }
  catch (error: unknown) {
    setResponseStatus(event, 500)
    const message = error instanceof Error ? error.message : 'An error occurred'
    return { detail: message }
  }
}

export default defineEventHandler(async (event): Promise<unknown> => {
  const { public: { apiBase } } = useRuntimeConfig()
  const fullPath = event.path.replace(/^\/api/, '') || '/'
  const path = fullPath.split('?')[0]
  const query = getQuery(event) as QueryObject

  const params = buildSearchParams(query)
  const queryString = params.toString()
  const url = `${apiBase}${path}${queryString ? `?${queryString}` : ''}`
  const format = query.format as string | undefined

  // For image/binary formats, fetch raw response and preserve content-type
  if (format === 'png' || format === 'svg') {
    return handleImageResponse(event, url, format)
  }

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
