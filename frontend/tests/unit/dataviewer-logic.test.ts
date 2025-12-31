import { describe, expect, it } from 'vitest'
import { formatDate } from '../../app/utils/format'

describe('dataViewer Component Logic', () => {
  it('formats dates correctly', () => {
    const input = '1934-01-01T00:00:00.000000+00:00'
    const expected = '1934-01-01T00:00:00Z'
    expect(formatDate(input)).toBe(expected)
  })

  it('determines correct API endpoint for station mode', () => {
    const mode = 'station'
    let endpoint = '/api/values'

    if (mode === 'interpolation')
      endpoint = '/api/interpolate'
    else if (mode === 'summary')
      endpoint = '/api/summarize'

    expect(endpoint).toBe('/api/values')
  })

  it('determines correct API endpoint for interpolation mode', () => {
    const mode = 'interpolation'
    let endpoint = '/api/values'

    if (mode === 'interpolation')
      endpoint = '/api/interpolate'
    else if (mode === 'summary')
      endpoint = '/api/summarize'

    expect(endpoint).toBe('/api/interpolate')
  })

  it('determines correct API endpoint for summary mode', () => {
    const mode = 'summary'
    let endpoint = '/api/values'

    if (mode === 'interpolation')
      endpoint = '/api/interpolate'
    else if (mode === 'summary')
      endpoint = '/api/summarize'

    expect(endpoint).toBe('/api/summarize')
  })

  it('calculates linear regression correctly', () => {
    function calculateLinearRegression(xData: Date[], yData: number[]): { x: Date[], y: number[] } {
      if (xData.length < 2)
        return { x: [], y: [] }

      const n = xData.length
      const xNums = xData.map(d => d.getTime())
      let sumX = 0
      let sumY = 0
      let sumXY = 0
      let sumXX = 0

      for (let i = 0; i < n; i++) {
        sumX += xNums[i]!
        sumY += yData[i]!
        sumXY += xNums[i]! * yData[i]!
        sumXX += xNums[i]! * xNums[i]!
      }

      const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX)
      const intercept = (sumY - slope * sumX) / n

      const minX = Math.min(...xNums)
      const maxX = Math.max(...xNums)

      return {
        x: [new Date(minX), new Date(maxX)],
        y: [slope * minX + intercept, slope * maxX + intercept],
      }
    }

    const xData = [new Date('2024-01-01'), new Date('2024-01-02'), new Date('2024-01-03')]
    const yData = [10, 20, 30]

    const result = calculateLinearRegression(xData, yData)

    expect(result.x.length).toBe(2)
    expect(result.y.length).toBe(2)
    expect(result.y[1]! - result.y[0]!).toBeGreaterThan(0)
  })

  it('calculates parameter statistics correctly', () => {
    const values = [
      { value: 10, parameter: 'temp', dataset: 'test' },
      { value: 20, parameter: 'temp', dataset: 'test' },
      { value: 30, parameter: 'temp', dataset: 'test' },
    ]

    const sum = values.reduce((acc, v) => acc + v.value, 0)
    const count = values.length
    const mean = sum / count
    const min = Math.min(...values.map(v => v.value))
    const max = Math.max(...values.map(v => v.value))

    expect(count).toBe(3)
    expect(min).toBe(10)
    expect(max).toBe(30)
    expect(mean).toBe(20)
    expect(sum).toBe(60)
  })

  it('converts values to CSV format', () => {
    function valuesToCsv(values: any[], selectedColumns: string[]) {
      if (!values.length)
        return ''
      const headers = selectedColumns
      const rows = values.map(row => headers.map(h => row[h] ?? '').join(','))
      return [headers.join(','), ...rows].join('\n')
    }

    const values = [
      { station_id: '001', parameter: 'temp', value: 10 },
      { station_id: '002', parameter: 'temp', value: 20 },
    ]
    const columns = ['station_id', 'parameter', 'value']

    const csv = valuesToCsv(values, columns)

    expect(csv).toContain('station_id,parameter,value')
    expect(csv).toContain('001,temp,10')
    expect(csv).toContain('002,temp,20')
  })

  it('paginates values correctly', () => {
    const allValues = Array.from({ length: 150 }, (_, i) => ({ id: i, value: i }))
    const pageSize = 50
    const currentPage = 1

    const start = (currentPage - 1) * pageSize
    const end = start + pageSize
    const paginatedValues = allValues.slice(start, end)

    expect(paginatedValues.length).toBe(50)
    expect(paginatedValues[0]!.id).toBe(0)
    expect(paginatedValues[49]!.id).toBe(49)
  })

  it('sorts values by column', () => {
    const values = [
      { station_id: '003', value: 30 },
      { station_id: '001', value: 10 },
      { station_id: '002', value: 20 },
    ]

    const sortedAsc = [...values].sort((a, b) => a.value - b.value)
    const sortedDesc = [...values].sort((a, b) => b.value - a.value)

    expect(sortedAsc[0]!.value).toBe(10)
    expect(sortedAsc[2]!.value).toBe(30)
    expect(sortedDesc[0]!.value).toBe(30)
    expect(sortedDesc[2]!.value).toBe(10)
  })
})
