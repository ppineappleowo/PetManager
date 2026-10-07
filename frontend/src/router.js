import { loadCurrentUser } from './composables/useCurrentUser.js'
import { createRouter, createWebHashHistory } from 'vue-router'
import { auth } from './composables/useAuth.js'

const router = createRouter({
  history: createWebHashHistory(),
  scrollBehavior(to, from, saved) { return saved || { top: 0 } },
  routes: [
    {path:'/discover',component:()=>import('./views/DiscoverView.vue')},
    {path:'/moderation',component:()=>import('./views/ModerationView.vue'),meta:{requiresAuth:true}},
    { path: '/reports', component: () => import('./views/ReportsView.vue'), meta: { requiresAuth: true } },
    { path: '/notifications', component: () => import('./views/NotificationsView.vue'), meta: { requiresAuth: true } },
    { path: '/bookmarks', component: () => import('./views/BookmarksView.vue'), meta: { requiresAuth: true } },
    { path: '/connections', component: () => import('./views/ConnectionsView.vue'), meta: { requiresAuth: true } },
    { path: '/following', component: () => import('./views/CommunityView.vue'), meta: { requiresAuth: true, following: true } },
    { path: '/pets', component: () => import('./views/PetsView.vue'), meta: { requiresAuth: true } },
    { path: '/pets/:id', component: () => import('./views/PetDetailView.vue') },
    { path: '/users/:id', component: () => import('./views/PublicProfileView.vue') },
    { path: '/', name: 'community', component: () => import('./views/CommunityView.vue') },
    { path: '/my-posts', name: 'my-posts', component: () => import('./views/CommunityView.vue'), meta: { requiresAuth: true, mine: true } },
    { path: '/posts/:id', component: () => import('./views/PostDetailView.vue') },
    { path: '/my-posts/:id', component: () => import('./views/PostDetailView.vue'), meta: { requiresAuth: true, mine: true } },
    { path: '/publish', component: () => import('./views/PostEditorView.vue'), meta: { requiresAuth: true } },
    { path: '/posts/:id/edit', component: () => import('./views/PostEditorView.vue'), meta: { requiresAuth: true } },
    { path: '/profile', name: 'profile', component: () => import('./views/ProfileView.vue'), meta: { requiresAuth: true } },
    { path: '/admin', name: 'admin', component: () => import('./views/AdminView.vue'), meta: { requiresAuth: true, admin: true } },
    { path: '/ai', name: 'chat', component: () => import('./views/ChatView.vue'), meta: { requiresAuth: true } },
    { path: '/login', name: 'login', component: () => import('./views/LoginView.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  if (to.meta.requiresAuth && !auth.token) return { name: 'login', query: { redirect: to.fullPath } }
  if (to.name === 'login' && auth.token) return { name: 'community' }
  if (to.meta.admin) {
    try { if ((await loadCurrentUser()).role !== 'admin') return { name: 'community' } }
    catch { return { name: auth.token ? 'community' : 'login' } }
  }
})
router.afterEach((to) => {
  document.title = to.name === 'admin' ? '管理后台 - 百宠集' : to.name === 'login' ? '登录 - 百宠集' : '百宠集 · 每一种宠爱，都有同好'
})
export default router
