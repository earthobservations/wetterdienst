<script setup lang="ts">
const { t } = useI18n()

// The maintainer's own words. Everything else on this page is a fact the repository already
// states; this paragraph is not, so it stays a marked placeholder rather than being invented.
//
// To fill it in: replace the string below with the text, then move it into the locale files as
// `about.maintainerBio` and translate it, the way every other string on this page is handled.
// The reminder banner disappears on its own once the « » markers are gone.
const maintainerBio = '«Ein paar Sätze über mich – Hintergrund, was ich mache, warum es Wetterdienst gibt.»'

const hasBioPlaceholder = computed(() => maintainerBio.includes('«'))

// Maintainer: the person who runs the project and the hosted instance at wetterdienst.eobs.org.
const maintainer = {
  name: 'Benjamin Gutzmann',
  email: 'benjamin@eobs.org',
  githubUsername: 'gutzbenj',
  githubAvatarId: '29654631',
  location: 'Hamburg',
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

          <p class="text-gray-600 dark:text-gray-400">
            {{ t('about.maintainerText1') }}
          </p>
          <p class="text-gray-600 dark:text-gray-400">
            {{ t('about.maintainerText2') }}
          </p>

          <UAlert
            v-if="hasBioPlaceholder"
            color="warning"
            variant="subtle"
            icon="i-lucide-triangle-alert"
            :title="t('about.bioPlaceholderNote')"
          />
          <p class="text-gray-600 dark:text-gray-400">
            {{ maintainerBio }}
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
