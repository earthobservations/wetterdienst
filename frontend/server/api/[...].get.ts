export default defineEventHandler(async (event) => {
    const {public: {apiBase}} = useRuntimeConfig()
    const fullPath = event.path.replace(/^\/api/, '') || '/'
    const path = fullPath.split('?')[0]
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
    const format = query.format as string | undefined

    // For image/binary formats, fetch raw response and preserve content-type
    if (format === 'png' || format === 'svg') {
        try {
            const response = await fetch(url, { method: 'GET' })

            if (format === 'png') {
                setResponseHeader(event, 'content-type', 'image/png')
                const arrayBuffer = await response.arrayBuffer()
                return send(event, new Uint8Array(arrayBuffer), 'image/png')
            }

            // SVG
            const svgText = await response.text()
            return send(event, svgText, 'image/svg+xml')
        } catch (error: any) {
            setResponseStatus(event, 500)
            return { detail: error?.message || 'An error occurred' }
        }
    }

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
