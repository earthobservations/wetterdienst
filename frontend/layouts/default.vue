<script setup>
// Import the sidebar component
// import Sidebar from '~/components/Sidebar.vue'
  const route = useRoute()
  const isSidebarOpen = useState("isSidebarOpen", () => true)

  const toggleSidebar = () => {
    isSidebarOpen.value = !isSidebarOpen.value
  }
</script>

<template>
  <div class="flex min-h-screen">
    <!-- Sidebar -->
    <aside :class="[
        'bg-gray-900 text-gray-100 flex flex-col p-6 space-y-4 transition-all duration-300',
        isSidebarOpen ? 'w-64' : 'w-20',
    ]">
      <Icon name="lucide:sidebar" @click="toggleSidebar" class="cursor-pointer text-2xl"/>
      <nav class="flex flex-col space-y-2">
        <NuxtLink
          to="/"
          class="block rounded hover:bg-gray-700 transition p-2 text-2xl"
          :class="{ 'bg-gray-800': route.path === '/' }"
        >
          <Icon name="lucide:house"/> {{isSidebarOpen ? ' Home' : ''}}
        </NuxtLink>
        <NuxtLink
          to="/explorer"
          class="block rounded hover:bg-gray-700 transition p-2 text-2xl"
          :class="{ 'bg-gray-800': route.path === '/explorer' }"
        >
          <Icon name="lucide:telescope"/> {{isSidebarOpen ? ' Explorer' : ''}}
        </NuxtLink>
      </nav>
    </aside>
    <!-- Page Content -->
    <main class="flex-1 bg-gray-100 text-gray-900 p-8 overflow-y-auto">
      <NuxtPage />
    </main>
  </div>
</template>

<style scoped>
/* Optional: make sidebar fixed if you want it to stay visible on scroll */
</style>