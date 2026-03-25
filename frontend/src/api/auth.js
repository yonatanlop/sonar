import client from './client'

export const authApi = {
  login: async (username, password) => {
    const form = new URLSearchParams()
    form.append('username', username)
    form.append('password', password)
    const { data } = await client.post('/auth/login', form, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    return data
  },

  getMe: () => client.get('/users/me').then(r => r.data),

  updateMe: (data) => client.put('/users/me', data).then(r => r.data),

  changePassword: (currentPassword, newPassword) =>
    client.post('/users/me/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    }),
}
