<script setup lang="ts">
const route = useRoute()

// useFetch is a composable that returns reactive data, not a promise
// so we don't use try/catch, instead we check error and data refs
const { data } = await useFetch('/api/', {
  query: route.query,
  method: 'GET'
})
</script>
<template>
</template>