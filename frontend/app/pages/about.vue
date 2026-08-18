<script setup lang="ts">
const { t } = useI18n()

// Counted rather than written down: an age is wrong from the next birthday onwards, and nobody
// remembers to edit it. Kept as parts rather than a Date, so parsing never lands on the wrong side
// of a timezone boundary and turns the birthday into the day before.
const BIRTHDAY = { year: 1993, month: 11, day: 28 }

const age = computed(() => {
  const now = new Date()
  const years = now.getFullYear() - BIRTHDAY.year
  const hadBirthday = now.getMonth() + 1 > BIRTHDAY.month
    || (now.getMonth() + 1 === BIRTHDAY.month && now.getDate() >= BIRTHDAY.day)
  return hadBirthday ? years : years - 1
})

// The two people the project is credited to. Both cards render from the same shape, so the
// co-author is not a lesser layout than the maintainer -- only the facts differ, and the optional
// meta line is what carries the ones that exist for one and not the other.
const people = computed(() => [
  {
    key: 'maintainer',
    name: 'Benjamin Gutzmann',
    role: t('about.maintainerRole'),
    // one paragraph: the sentences read on from each other
    bio: `${t('about.maintainerBio')} ${t('about.maintainerText2')}`,
    githubAvatarId: '29654631',
    meta: [
      { icon: 'i-lucide-map-pin', text: 'Hamburg' },
      { icon: 'i-lucide-cake', text: t('about.maintainerAge', { age: age.value }) },
    ],
    links: [
      { icon: 'i-lucide-github', label: 'gutzbenj', to: 'https://github.com/gutzbenj' },
      { icon: 'i-lucide-mail', label: 'benjamin@eobs.org', to: 'mailto:benjamin@eobs.org' },
      { icon: 'i-lucide-linkedin', label: 'LinkedIn', to: 'https://www.linkedin.com/in/benjamin-gutzmann-3792b1141/' },
      // rel="me" is what lets the Mastodon profile verify a link back to this site
      { icon: 'i-simple-icons-mastodon', label: '@gutzb3nj', to: 'https://mastodon.social/@gutzb3nj', rel: 'me noopener noreferrer' },
    ],
  },
  {
    key: 'coauthor',
    name: 'Andreas Motl',
    role: t('about.coAuthorRole'),
    bio: t('about.coAuthorBio'),
    githubAvatarId: '453543',
    // the city comes from the maintainer, who works with him; there is no age here because
    // Andreas has not published one, and his is not ours to go looking for
    meta: [
      { icon: 'i-lucide-map-pin', text: 'Berlin' },
    ],
    links: [
      { icon: 'i-lucide-github', label: 'amotl', to: 'https://github.com/amotl' },
      { icon: 'i-lucide-mail', label: 'andreas.motl@panodata.org', to: 'mailto:andreas.motl@panodata.org' },
    ],
  },
])
</script>

<template>
  <UContainer class="mx-auto max-w-3xl px-4 py-6 space-y-6">
    <div class="text-center mb-8">
      <h1 class="text-3xl font-bold mb-4">
        {{ t('about.title') }}
      </h1>
      <p class="text-gray-600 dark:text-gray-400">
        {{ t('about.subtitle') }}
      </p>
    </div>

    <UCard>
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-info" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ t('about.projectTitle') }}
          </h2>
        </div>
      </template>
      <p class="text-gray-600 dark:text-gray-400 mb-4">
        {{ t('about.projectText1') }}
      </p>
      <p class="text-gray-600 dark:text-gray-400 mb-4">
        {{ t('about.projectText2') }}
      </p>
      <p class="text-gray-600 dark:text-gray-400">
        {{ t('about.projectText3') }}
      </p>
    </UCard>

    <!-- Both people in one section rather than a card each: a card header per person repeated the
         role line beneath it ("Maintainer" over "Creator and maintainer"), and a bare heading
         between two carded sections broke the rhythm of the page. One card, one heading, a rule
         between the two of them. -->
    <UCard>
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-users" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ t('about.peopleTitle') }}
          </h2>
        </div>
      </template>

      <div
        v-for="(person, index) in people"
        :key="person.key"
        :class="index > 0 ? 'mt-6 pt-6 border-t border-gray-200 dark:border-gray-800' : ''"
      >
        <div class="flex flex-col sm:flex-row gap-6">
          <div class="flex flex-col items-center gap-2 shrink-0">
            <a
              :href="person.links[0]?.to"
              target="_blank"
              class="group"
            >
              <img
                :src="`https://avatars.githubusercontent.com/u/${person.githubAvatarId}`"
                :alt="person.name"
                class="w-24 h-24 rounded-full ring-2 ring-gray-200 dark:ring-gray-700 group-hover:ring-primary-500 transition-all"
              >
            </a>
            <span
              v-for="item in person.meta"
              :key="item.text"
              class="text-sm text-gray-500 dark:text-gray-400 flex items-center gap-1"
            >
              <UIcon :name="item.icon" class="shrink-0" />
              {{ item.text }}
            </span>
          </div>

          <div class="flex-1 space-y-3">
            <div>
              <h3 class="text-xl font-bold">
                {{ person.name }}
              </h3>
              <p class="text-sm text-primary-600 dark:text-primary-400 font-medium">
                {{ person.role }}
              </p>
            </div>

            <p class="text-gray-600 dark:text-gray-400">
              {{ person.bio }}
            </p>

            <div class="flex flex-wrap gap-2 pt-1">
              <UButton
                v-for="link in person.links"
                :key="link.to"
                :to="link.to"
                :target="link.to.startsWith('mailto:') ? undefined : '_blank'"
                :rel="link.rel"
                size="sm"
                variant="outline"
                :icon="link.icon"
              >
                {{ link.label }}
              </UButton>
            </div>

            <p v-if="person.key === 'coauthor'" class="text-sm text-gray-600 dark:text-gray-400">
              {{ t('about.contributorsText') }}
              <a
                href="https://github.com/earthobservations/wetterdienst/blob/main/CONTRIBUTORS.md"
                target="_blank"
                class="text-primary-500 hover:underline"
              >
                {{ t('about.contributorsLink') }}
              </a>
            </p>
          </div>
        </div>
      </div>
    </UCard>

    <UCard>
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-link" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ t('about.linksTitle') }}
          </h2>
        </div>
      </template>
      <div class="flex flex-wrap gap-2">
        <UButton
          to="https://github.com/earthobservations/wetterdienst"
          target="_blank"
          size="sm"
          variant="outline"
          icon="i-lucide-github"
        >
          {{ t('about.linkSource') }}
        </UButton>
        <UButton
          to="https://wetterdienst.readthedocs.io/"
          target="_blank"
          size="sm"
          variant="outline"
          icon="i-lucide-book-open"
        >
          {{ t('about.linkDocs') }}
        </UButton>
        <UButton
          to="https://pypi.org/project/wetterdienst"
          target="_blank"
          size="sm"
          variant="outline"
          icon="i-lucide-package"
        >
          {{ t('about.linkPypi') }}
        </UButton>
        <UButton
          to="/support"
          size="sm"
          variant="outline"
          icon="i-lucide-heart"
        >
          {{ t('about.linkSupport') }}
        </UButton>
      </div>
    </UCard>
  </UContainer>
</template>
