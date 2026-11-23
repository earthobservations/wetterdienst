import { localizedCredit } from '~/utils/provider-credit'

/**
 * Writes a provider's credit line with its leading label ("Source:") in the language of the page (GH-4333): the label is the app's,
 * the words after it are the provider's own. Call it inside a computed or a template, so that it follows a change of language.
 */
export function useCreditLine() {
  const { t } = useI18n()
  return (attribution: string | null | undefined): string => attribution
    ? localizedCredit(attribution, { source: t('credit.source'), dataSource: t('credit.dataSource'), colon: t('common.colon') })
    : ''
}
