<script setup lang="ts">
import type { Section } from '~/utils/sections'
import type { MoveNote } from '~/utils/tab-bar'
import { TOOLS } from '~/utils/sections'
import { BAR_SIZE, describeMove, moveTool, slotAt } from '~/utils/tab-bar'

// The choice of the four tools in the phone's tab bar (GH-3846, on the settings page): all the tools in one list, the
// four of the bar above a line and the ones that are only in the Menu below it, and a preview of the bar that follows
// the list, also while a tool is being dragged. A tool moves by its handle (a pointer: mouse, finger, pen), and by the
// arrow buttons on its row, which do all that dragging does and are the way for a keyboard and a screen reader
// (WCAG 2.5.7 Dragging Movements, 2.1.1): a move by them is said in a polite status, and the focus stays on the button
// that was pressed, though its row is built again where it crosses the line.
//
// Only the handle starts a drag and holds `touch-action: none`, so a finger anywhere else scrolls the sheet or the
// page. While a tool is dragged the rows stay where they are (a row that moved in the document would lose the pointer
// that holds it): the row it will land on is marked with a bar at its edge, and the preview shows the bar as it would
// be after a drop. The drop makes the move; Escape and a cancelled pointer leave the list as it was. The list is the
// reader's `settings.tabBar` through `useTabBar`, so the bar the chooser previews is the bar that is drawn.
//
// There is no drag library: five rows of one height are a list that `slotAt` reads the place of a pointer in, and the
// few lines this takes are less than a dependency would add to the bundle, the licence list and the audit (and
// none of the libraries, SortableJS or the like, announces a move or has an alternative to dragging).
const { t } = useI18n()
const { order, setOrder, resetOrder } = useTabBar()

const byKey = (key: string): Section => TOOLS.find(tool => tool.key === key)!
const name = (key: string) => t(byKey(key).label)
const names = (keys: readonly string[]) => keys.map(name).join(', ')

// The tool that is being dragged and the place it would be dropped on. The list that is drawn stays `order`; `shown`
// is what it would be after a drop, which the preview draws.
const drag = ref<{ key: string, pointerId: number, target: number } | null>(null)
const shown = computed(() => drag.value
  ? moveTool(order.value, order.value.indexOf(drag.value.key), drag.value.target)
  : order.value)
const previewBar = computed(() => shown.value.slice(0, BAR_SIZE))
const previewMenu = computed(() => shown.value.slice(BAR_SIZE))

const groups = computed(() => [
  { id: 'bar', label: t('settings.bar.inBar'), keys: order.value.slice(0, BAR_SIZE), first: 0 },
  { id: 'menu', label: t('settings.bar.inMenu'), keys: order.value.slice(BAR_SIZE), first: BAR_SIZE },
].filter(group => group.keys.length))

/** Where the row at `index` would be dropped on, for the bar that marks it: before the row when the tool comes from below it, after it when from above */
function dropMark(index: number): 'before' | 'after' | undefined {
  if (!drag.value || drag.value.target !== index)
    return undefined
  const from = order.value.indexOf(drag.value.key)
  return index < from ? 'before' : index > from ? 'after' : undefined
}

// what a move did, in words, in a status that a screen reader reads out when it changes
const announcement = ref('')
function say(note: MoveNote) {
  return t(`settings.bar.${note.kind}`, {
    tool: name(note.tool),
    other: note.other ? name(note.other) : '',
    position: note.position,
    total: note.total,
  })
}

function apply(key: string, next: string[]) {
  const note = describeMove(order.value, next, key)
  if (!note)
    return
  setOrder(next)
  announcement.value = say(note)
}

const root = useTemplateRef<HTMLElement>('root')

/** One place up (`-1`) or down (`1`), by the buttons of a row */
async function step(key: string, delta: -1 | 1) {
  const at = order.value.indexOf(key)
  const to = at + delta
  if (to < 0 || to >= order.value.length)
    return
  apply(key, moveTool(order.value, at, to))
  // the row is built again where it crosses the line, and a button that took the focus away with it gives it back to
  // the same button of the row where the tool now is (a button that has come to the end of the list stays, and says
  // it is unavailable)
  await nextTick()
  root.value?.querySelector<HTMLElement>(`[data-tool="${key}"] [data-dir="${delta < 0 ? 'up' : 'down'}"]`)?.focus()
}

function reset() {
  resetOrder()
  announcement.value = t('settings.bar.resetDone', { tools: names(order.value.slice(0, BAR_SIZE)) })
}

function rowRects() {
  return [...(root.value?.querySelectorAll<HTMLElement>('[data-row]') ?? [])].map(row => row.getBoundingClientRect())
}

function onPointerDown(event: PointerEvent, key: string) {
  if (drag.value || (event.pointerType === 'mouse' && event.button !== 0))
    return
  // the handle keeps the pointer for the drag, wherever it goes, and the text under it is not selected
  const handle = event.currentTarget as HTMLElement
  handle.setPointerCapture(event.pointerId)
  event.preventDefault()
  drag.value = { key, pointerId: event.pointerId, target: order.value.indexOf(key) }
}

function onPointerMove(event: PointerEvent) {
  if (drag.value?.pointerId === event.pointerId)
    drag.value.target = slotAt(event.clientY, rowRects())
}

function onPointerUp(event: PointerEvent) {
  const current = drag.value
  if (current?.pointerId !== event.pointerId)
    return
  const target = slotAt(event.clientY, rowRects())
  drag.value = null
  apply(current.key, moveTool(order.value, order.value.indexOf(current.key), target))
}

function cancelDrag(event?: PointerEvent) {
  if (!event || drag.value?.pointerId === event.pointerId)
    drag.value = null
}

// Escape drops nothing, as in every other drag
useEventListener('keydown', (event: KeyboardEvent) => {
  if (drag.value && event.key === 'Escape') {
    event.preventDefault()
    drag.value = null
  }
})
</script>

<template>
  <div ref="root" class="space-y-5" :class="{ 'bar-dragging': drag }" data-testid="bar-chooser">
    <p class="text-sm text-muted">
      {{ t('settings.bar.hint') }}
    </p>

    <!-- stays in view under the header while the list is scrolled or dragged, so the result is always seen -->
    <div class="bar-sticky">
      <div class="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted">
        {{ t('settings.bar.preview') }}
      </div>
      <!-- the bar as it is on a phone, the same tiles and labels; a picture, named by what it shows -->
      <div
        class="bar-preview"
        role="img"
        :aria-label="t('settings.bar.previewLabel', { tools: names(previewBar) })"
        data-testid="bar-preview"
      >
        <div
          v-for="key in previewBar"
          :key="key"
          class="tabbar-item bar-preview-item"
          :data-moving="drag?.key === key ? '' : undefined"
          :data-preview-tool="key"
        >
          <ToolTile :tile="byKey(key).tile" :icon="byKey(key).icon" size="1.625rem" />
          <span class="tabbar-label">{{ name(key) }}</span>
        </div>
        <div class="tabbar-item">
          <span class="tile tile-navy" style="--tile-size: 1.625rem" aria-hidden="true"><UIcon name="i-ph-dots-three-outline-fill" /></span>
          <span class="tabbar-label">{{ t('header.menu') }}</span>
        </div>
      </div>
      <p v-if="previewMenu.length" class="mt-1.5 text-sm text-muted" aria-hidden="true" data-testid="bar-preview-menu">
        {{ t('settings.bar.menuOnly', { tools: names(previewMenu) }) }}
      </p>
    </div>

    <p class="text-sm">
      {{ t('settings.bar.instructions') }}
    </p>

    <div v-for="group in groups" :key="group.id" :class="group.id === 'menu' ? 'bar-line' : undefined" :data-testid="`bar-group-${group.id}`">
      <h3 :id="`bar-heading-${group.id}`" class="mb-2 text-sm font-semibold">
        {{ group.label }}
      </h3>
      <ol class="space-y-2" :aria-labelledby="`bar-heading-${group.id}`">
        <li
          v-for="(key, position) in group.keys"
          :key="key"
          class="bar-row"
          data-row
          :data-tool="key"
          :data-dragging="drag?.key === key ? '' : undefined"
          :data-drop="dropMark(group.first + position)"
        >
          <!-- the pointer's way, which the buttons make no part of: not a stop of the keyboard, and not read out -->
          <span
            class="bar-handle"
            aria-hidden="true"
            data-testid="bar-handle"
            @pointerdown="onPointerDown($event, key)"
            @pointermove="onPointerMove"
            @pointerup="onPointerUp"
            @pointercancel="cancelDrag"
            @lostpointercapture="cancelDrag"
          >
            <UIcon name="i-ph-dots-six-vertical-bold" class="size-5" />
          </span>
          <ToolTile :tile="byKey(key).tile" :icon="byKey(key).icon" size="2rem" />
          <span class="min-w-0 flex-1 break-words font-semibold">{{ name(key) }}</span>
          <button
            type="button"
            class="bar-move"
            data-dir="up"
            :aria-label="t('settings.bar.moveUp', { tool: name(key) })"
            :aria-disabled="group.first + position === 0 ? 'true' : undefined"
            @click="step(key, -1)"
          >
            <UIcon name="i-ph-arrow-up-bold" class="size-5" aria-hidden="true" />
          </button>
          <button
            type="button"
            class="bar-move"
            data-dir="down"
            :aria-label="t('settings.bar.moveDown', { tool: name(key) })"
            :aria-disabled="group.first + position === order.length - 1 ? 'true' : undefined"
            @click="step(key, 1)"
          >
            <UIcon name="i-ph-arrow-down-bold" class="size-5" aria-hidden="true" />
          </button>
        </li>
      </ol>
    </div>

    <div class="flex">
      <UButton
        :label="t('settings.bar.reset')"
        icon="i-ph-arrow-counter-clockwise"
        color="neutral"
        variant="outline"
        size="sm"
        data-testid="bar-reset"
        @click="reset"
      />
    </div>

    <!-- what a move did: read out when it changes, here from the start so that the first one is -->
    <p class="sr-only" role="status" aria-live="polite" data-testid="bar-status">
      {{ announcement }}
    </p>
  </div>
</template>
