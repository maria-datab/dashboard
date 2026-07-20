import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('./views/HomeView.vue'),
  },
  {
    path: '/boxout/:pathMatch(.*)*',
    name: 'boxout',
    component: () => import('@dashboard/boxout/App.vue'),
  },
  {
    path: '/simple-parts/:pathMatch(.*)*',
    name: 'simple-parts',
    component: () => import('@dashboard/simple-parts/App.vue'),
  },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
