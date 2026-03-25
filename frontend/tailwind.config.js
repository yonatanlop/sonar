/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Paleta principal SONAR
        primary: {
          50:  '#eff6ff',
          100: '#dbeafe',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          900: '#1e3a8a',
        },
        // Severidades de alerta
        critical: '#dc2626',
        high:     '#ea580c',
        medium:   '#d97706',
        low:      '#2563eb',
      },
    },
  },
  plugins: [],
}
