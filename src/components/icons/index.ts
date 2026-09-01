import type { Component } from 'vue'
import BaseIcon from './BaseIcon.vue'
import IconClose from './IconClose.vue'
import IconCheck from './IconCheck.vue'
import IconHeart from './IconHeart.vue'
import IconHeartFilled from './IconHeartFilled.vue'
import IconSearch from './IconSearch.vue'
import IconInfo from './IconInfo.vue'
import IconMore from './IconMore.vue'
import IconArrowLeft from './IconArrowLeft.vue'
import IconArrowRight from './IconArrowRight.vue'
import IconArrowUp from './IconArrowUp.vue'
import IconChevronDown from './IconChevronDown.vue'
import IconChevronUp from './IconChevronUp.vue'
import IconMenu from './IconMenu.vue'
import IconUpload from './IconUpload.vue'
import IconDownload from './IconDownload.vue'
import IconCamera from './IconCamera.vue'
import IconExternalLink from './IconExternalLink.vue'
import IconRefresh from './IconRefresh.vue'
import IconPlus from './IconPlus.vue'
import IconMinus from './IconMinus.vue'
import IconLock from './IconLock.vue'
import IconUnlock from './IconUnlock.vue'
import IconBookOpen from './IconBookOpen.vue'
import IconEye from './IconEye.vue'
import IconEyeOff from './IconEyeOff.vue'
import IconArchive from './IconArchive.vue'
import IconTrash from './IconTrash.vue'
import IconUsers from './IconUsers.vue'
import IconCopy from './IconCopy.vue'
import IconLogOut from './IconLogOut.vue'
import IconPause from './IconPause.vue'
import IconPlay from './IconPlay.vue'
import type { IconName, IconSize } from './types'

export {
  BaseIcon,
  IconClose,
  IconCheck,
  IconHeart,
  IconHeartFilled,
  IconSearch,
  IconInfo,
  IconMore,
  IconArrowLeft,
  IconArrowRight,
  IconArrowUp,
  IconChevronDown,
  IconChevronUp,
  IconMenu,
  IconUpload,
  IconDownload,
  IconCamera,
  IconExternalLink,
  IconRefresh,
  IconPlus,
  IconMinus,
  IconLock,
  IconUnlock,
  IconBookOpen,
  IconEye,
  IconEyeOff,
  IconArchive,
  IconTrash,
  IconUsers,
  IconCopy,
  IconLogOut,
  IconPause,
  IconPlay,
}
export type { IconSize, IconName }

export const ICON_MAP: Record<IconName, Component> = {
  close: IconClose,
  check: IconCheck,
  heart: IconHeart,
  'heart-filled': IconHeartFilled,
  search: IconSearch,
  info: IconInfo,
  more: IconMore,
  'arrow-left': IconArrowLeft,
  'arrow-right': IconArrowRight,
  'arrow-up': IconArrowUp,
  'chevron-down': IconChevronDown,
  'chevron-up': IconChevronUp,
  menu: IconMenu,
  upload: IconUpload,
  download: IconDownload,
  camera: IconCamera,
  'external-link': IconExternalLink,
  refresh: IconRefresh,
  plus: IconPlus,
  minus: IconMinus,
  lock: IconLock,
  unlock: IconUnlock,
  'book-open': IconBookOpen,
  eye: IconEye,
  'eye-off': IconEyeOff,
  archive: IconArchive,
  trash: IconTrash,
  users: IconUsers,
  copy: IconCopy,
  logout: IconLogOut,
  pause: IconPause,
  play: IconPlay,
}
