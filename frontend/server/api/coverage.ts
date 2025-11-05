export default defineEventHandler(async (event) => {
    const { public: { apiBase } } = useRuntimeConfig()
    const query = getQuery(event) || {}
    // build URL search string (handles arrays)
    const params = new URLSearchParams()
    Object.entries(query).forEach(([key, val]) => {
        if (val === undefined || val === null) return
        if (Array.isArray(val)) {
            val.forEach(v => params.append(key, String(v)))
        } else {
            params.append(key, String(val))
        }
    }
    )
    const url = `${apiBase}/coverage?${params.toString()}`
  try {
    const response = await $fetch(url, { method: 'GET' })
    return response
  } catch (err: any) {
    console.log(err)
    const body = err.data ?? err.response?.data ?? { message: err.message }
    const statusMessage = typeof body === 'string'
      ? body
      : (body?.detail ?? body?.message ?? JSON.stringify(body))
    const statusCode = err.status ?? err.response?.status ?? 500
    throw createError({
      statusCode,
      statusMessage,
      data: body
    })
  }
}
)