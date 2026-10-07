export function usernameError(value) {
  const text = value.trim()
  if (text.length < 2 || text.length > 32) return '用户名长度需在 2-32 个字符'
  return /^[a-zA-Z0-9_一-鿿]+$/.test(text) ? '' : '只能包含字母、数字、下划线或中文'
}

export function passwordError(value) {
  if (value.length < 6 || value.length > 64) return '密码长度需在 6-64 个字符'
  return value.trim() ? '' : '密码不能全部为空格'
}
