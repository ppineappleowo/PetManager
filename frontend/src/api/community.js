import { apiJson, baseUrl } from './client.js'
export const categories = { cat: '猫咪', dog: '狗狗', bird: '鸟类', fish: '鱼类', small: '小宠', reptile: '爬宠', other: '其他', general: '多宠 / 综合' }
export const commonTags = ['晒宠日常', '新手养宠', '饮食', '健康', '出游', '领养故事']
export const community = (path, options) => apiJson('/api/v1/community' + path, options)
export const imageUrl = (post, image, thumbnail = false) => `${baseUrl}/api/v1/community/posts/${post}/images/${image}?thumbnail=${thumbnail}`
export const statusLabel = (status) => ({ published: '已发布', hidden: '已下架', deleted: '已删除' }[status] || status)
