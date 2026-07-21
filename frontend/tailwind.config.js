/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        iq: {
          navy:      '#005487',
          blue:      '#00A3E0',
          orange:    '#FE8A12',
          green:     '#6CC04A',
          lightblue: '#7FA9C3',
          bg:        '#F2F5F8',
          surface:   '#FFFFFF',
          border:    '#D2DADF',
          text:      '#2B3A42',
          muted:     '#6B7A85',
        },
        // keep navy/brand aliases so any remaining utility classes compile
        navy: {
          950: '#F2F5F8',
          900: '#F2F5F8',
          800: '#FFFFFF',
          700: '#E8EEF3',
          600: '#D2DADF',
        },
        brand: {
          DEFAULT: '#00A3E0',
          dark:    '#005487',
          cyan:    '#7FA9C3',
          glow:    'rgba(0,163,224,0.2)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      backdropBlur: { xs: '2px' },
      boxShadow: {
        glow:   '0 0 20px rgba(0,163,224,0.2)',
        'glow-sm': '0 0 10px rgba(0,163,224,0.15)',
        card:   '0 1px 4px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04)',
        'card-md': '0 4px 12px rgba(0,0,0,0.08), 0 8px 24px rgba(0,0,0,0.06)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.4s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
      },
      keyframes: {
        fadeIn:  { '0%': { opacity: '0' }, '100%': { opacity: '1' } },
        slideUp: { '0%': { opacity: '0', transform: 'translateY(12px)' }, '100%': { opacity: '1', transform: 'translateY(0)' } },
      },
    },
  },
  plugins: [],
}
