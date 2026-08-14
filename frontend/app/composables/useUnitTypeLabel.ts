/**
 * Names the quantity a parameter is measured in -- "angle", "energy_per_area", "wind_scale" as the
 * backend spells them -- in the active language.
 *
 * The catalog keys are camelCased (`unitEnergyPerArea`), so the backend's snake_case is converted
 * rather than listed twice. A type with no entry falls back to its raw id with the underscores
 * removed, which is what the glossary filter used to show for every type in every language.
 */
export function useUnitTypeLabel() {
  const { t, te } = useI18n()

  function unitTypeLabel(type: string): string {
    const key = `settings.unit${type.replace(/(?:^|_)(\w)/g, (_, c: string) => c.toUpperCase())}`
    return te(key) ? t(key) : type.replace(/_/g, ' ')
  }

  return { unitTypeLabel }
}
