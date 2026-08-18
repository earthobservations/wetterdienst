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

// Maintainer: the person who runs the project and the hosted instance at wetterdienst.eobs.org.
const maintainer = {
  name: 'Benjamin Gutzmann',
  email: 'benjamin@eobs.org',
  githubUsername: 'gutzbenj',
  githubAvatarId: '29654631',
  location: 'Hamburg',
  linkedin: 'https://www.linkedin.com/in/benjamin-gutzmann-3792b1141/',
  mastodon: 'https://mastodon.social/@gutzb3nj',
  mastodonHandle: '@gutzb3nj',
}

// Co-author, listed flat on purpose: name, avatar and how to reach him, no write-up.
const coAuthor = {
  name: 'Andreas Motl',
  email: 'andreas.motl@panodata.org',
  githubUsername: 'amotl',
  githubAvatarId: '453543',
}
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

    <UCard>
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-user" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ t('about.maintainerTitle') }}
          </h2>
        </div>
      </template>

      <div class="flex flex-col sm:flex-row gap-6">
        <div class="flex flex-col items-center gap-2 shrink-0">
          <a
            :href="`https://github.com/${maintainer.githubUsername}`"
            target="_blank"
            class="group"
          >
            <img
              :src="`https://avatars.githubusercontent.com/u/${maintainer.githubAvatarId}`"
              :alt="maintainer.name"
              class="w-24 h-24 rounded-full ring-2 ring-gray-200 dark:ring-gray-700 group-hover:ring-primary-500 transition-all"
            >
          </a>
          <span class="text-sm text-gray-500 dark:text-gray-400 flex items-center gap-1">
            <UIcon name="i-lucide-map-pin" class="shrink-0" />
            {{ maintainer.location }}
          </span>
          <span class="text-sm text-gray-500 dark:text-gray-400 flex items-center gap-1">
            <UIcon name="i-lucide-cake" class="shrink-0" />
            {{ t('about.maintainerAge', { age }) }}
          </span>
        </div>

        <div class="flex-1 space-y-3">
          <div>
            <h3 class="text-xl font-bold">
              {{ maintainer.name }}
            </h3>
            <p class="text-sm text-primary-600 dark:text-primary-400 font-medium">
              {{ t('about.maintainerRole') }}
            </p>
          </div>

          <!-- one paragraph, two strings: the sentences read on from each other, and a break
               between them left the card looking like two half-written blocks -->
          <p class="text-gray-600 dark:text-gray-400">
            {{ t('about.maintainerBio') }} {{ t('about.maintainerText2') }}
          </p>

          <div class="flex flex-wrap gap-2 pt-1">
            <UButton
              :to="`https://github.com/${maintainer.githubUsername}`"
              target="_blank"
              size="sm"
              variant="outline"
              icon="i-lucide-github"
            >
              {{ maintainer.githubUsername }}
            </UButton>
            <UButton
              :to="`mailto:${maintainer.email}`"
              size="sm"
              variant="outline"
              icon="i-lucide-mail"
            >
              {{ maintainer.email }}
            </UButton>
            <UButton
              :to="maintainer.linkedin"
              target="_blank"
              size="sm"
              variant="outline"
              icon="i-lucide-linkedin"
            >
              LinkedIn
            </UButton>
            <!-- rel="me" is what lets the Mastodon profile verify a link back to this site, so it
                 is spelled out rather than left to the default rel for a _blank link. The icon
                 comes from simple-icons because Lucide has no mastodon glyph; icons are resolved
                 through Iconify either way, so this costs no new dependency. -->
            <UButton
              :to="maintainer.mastodon"
              target="_blank"
              rel="me noopener noreferrer"
              size="sm"
              variant="outline"
              icon="i-simple-icons-mastodon"
            >
              {{ maintainer.mastodonHandle }}
            </UButton>
          </div>
        </div>
      </div>
    </UCard>

    <UCard>
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-users" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ t('about.coAuthorTitle') }}
          </h2>
        </div>
      </template>
      <div class="flex items-center gap-4">
        <a
          :href="`https://github.com/${coAuthor.githubUsername}`"
          target="_blank"
          class="group shrink-0"
        >
          <img
            :src="`https://avatars.githubusercontent.com/u/${coAuthor.githubAvatarId}`"
            :alt="coAuthor.name"
            class="w-12 h-12 rounded-full ring-2 ring-gray-200 dark:ring-gray-700 group-hover:ring-primary-500 transition-all"
          >
        </a>
        <div>
          <p class="font-medium">
            {{ coAuthor.name }}
          </p>
          <a
            :href="`mailto:${coAuthor.email}`"
            class="text-sm text-gray-500 dark:text-gray-400 hover:text-primary-500 transition-colors"
          >
            {{ coAuthor.email }}
          </a>
        </div>
      </div>
      <p class="text-sm text-gray-600 dark:text-gray-400 mt-4">
        {{ t('about.contributorsText') }}
        <a
          href="https://github.com/earthobservations/wetterdienst/blob/main/CONTRIBUTORS.md"
          target="_blank"
          class="text-primary-500 hover:underline"
        >
          {{ t('about.contributorsLink') }}
        </a>
      </p>
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
