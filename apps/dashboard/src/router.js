import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('./views/HomeView.vue'),
  },
  {
    path: '/boxout',
    name: 'boxout',
    component: () => import('./views/ToolFrameView.vue'),
    props: {
      title: 'DoorBoxOut',
      originEnvKey: 'VITE_BOXOUT_ORIGIN',
      defaultOrigin: 'http://127.0.0.1:5174',
    },
  },
  {
    path: '/simple-parts',
    name: 'simple-parts',
    component: () => import('./views/ToolFrameView.vue'),
    props: {
      title: 'Simple Parts',
      originEnvKey: 'VITE_SIMPLE_PARTS_ORIGIN',
      defaultOrigin: 'http://127.0.0.1:5175',
    },
  },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
