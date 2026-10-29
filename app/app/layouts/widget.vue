<template>
  <!-- the widget is embedded by other sites: no header, no footer, nothing around the page. Its colours and its font are those of the
       new look (GH-3518), and it draws its own background, so it reads on whatever page frames it -->
  <UMain>
    <slot />
  </UMain>
</template>
