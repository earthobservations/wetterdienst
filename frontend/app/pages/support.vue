<script setup lang="ts">
</script>
<template>
  <UContainer class="max-w-3xl mx-auto py-8 px-4">
  <div class="flex items-center gap-3 mb-6">
    <UIcon name="i-lucide-heart" class="text-2xl text-primary-500" />
    <h1 class="text-3xl font-bold">Support</h1>
  </div>

  <UCard class="mb-4">
    <template #header>
      <h2 class="text-lg font-semibold">Report Issues</h2>
    </template>
    <p class="text-gray-600 dark:text-gray-400">Found a bug? Please open an issue on GitHub with a minimal reproduction and steps to reproduce.</p>
    <div class="mt-3">
      <UButton size="sm" variant="ghost" color="primary" to="https://github.com/earthobservations/wetterdienst/issues" target="_blank">Open an Issue</UButton>
    </div>
  </UCard>

  <UCard class="mb-4">
    <template #header>
      <h2 class="text-lg font-semibold">Contribute</h2>
    </template>
    <p class="text-gray-600 dark:text-gray-400">Contributions are welcome via pull requests. Please follow the contribution guidelines in the repository.</p>
    <div class="mt-3">
      <UButton size="sm" variant="ghost" color="primary" to="https://github.com/earthobservations/wetterdienst/pulls" target="_blank">Create a Pull Request</UButton>
    </div>
  </UCard>

  <UCard class="mb-4">
    <template #header>
      <h2 class="text-lg font-semibold">Discussions</h2>
    </template>
    <p class="text-gray-600 dark:text-gray-400">For general questions, feature requests, or community discussion, please use GitHub Discussions.</p>
    <div class="mt-3">
      <UButton size="sm" variant="ghost" color="primary" to="https://github.com/earthobservations/wetterdienst/discussions" target="_blank">Go to Discussions</UButton>
    </div>
    </UCard>

    <UCard>
      <template #header>
      <h2 class="text-lg font-semibold">Support the Project</h2>
    </template>
      <p class="text-gray-600 dark:text-gray-400">If you find the project useful, consider supporting us via donations or sponsorships.</p>
      <div class="mt-3">
      <ul class="space-y-2 text-gray-700 dark:text-gray-300">
        <li class="flex items-center gap-2"><UIcon name="i-simple-icons-github" class="size-4" /><a href="https://github.com/sponsors/gutzbenj" target="_blank" class="text-primary-500 hover:underline">gutzbenj</a></li>
        <li class="flex items-center gap-2"><UIcon name="i-simple-icons-paypal" class="size-4" /><a href="https://paypal.me/BenjaminGutzmann" target="_blank" class="text-primary-500 hover:underline">paypal.me/BenjaminGutzmann</a></li>
      </ul>
    </div>
    </UCard>
  </UContainer>

</template>
