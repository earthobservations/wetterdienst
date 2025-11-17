export default defineEventHandler(async (event) => {
    const {public: {apiBase}} = useRuntimeConfig()
    const path = event.path.replace(/^\/api/, '') || '/'
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
    })

    const queryString = params.toString()
    const url = `${apiBase}${path}${queryString ? '?' + queryString : ''}`

    try {
        return await $fetch(url, {method: 'GET'})
    } catch (error: any) {
        // Return FastAPI-compatible error format
        const statusCode = error?.response?.status || error?.status || 500
        setResponseStatus(event, statusCode)

        // If the backend returned FastAPI error format, pass it through
        if (error?.data) {
            return error.data
        }

        // Otherwise, create FastAPI-compatible error response
        return {
            detail: error?.message || 'An error occurred'
        }
    }
}
)
