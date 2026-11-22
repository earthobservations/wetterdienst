/** A backend id as words (`temperature_dew_point` as `Temperature Dew Point`): what a label falls back to where the glossary has none */
export function prettifyId(id: string): string {
  return id
    .replace(/_/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, c => c.toUpperCase())
}
