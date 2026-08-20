/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // OVIX Dark Premium Palette
        background: {
          DEFAULT: '#0a0a0a',      // Deep black for main background
          surface: '#111111',        // Anthracite for surfaces
          card: '#161616',          // Dark for cards and panels
          elevated: '#1a1a1a',       // Slightly elevated cards
          modal: '#202020',         // Modal/dialog backgrounds
        },
        border: {
          DEFAULT: '#2a2a2a',        // Medium gray for borders
          subtle: '#222222',         // Subtle borders
          strong: '#333333',        // Strong borders
        },
        text: {
          DEFAULT: '#ffffff',        // Off-white for main text
          primary: '#f5f5f5',       // Primary text
          secondary: '#a0a0a0',     // Secondary text
          tertiary: '#666666',      // Tertiary text
          muted: '#444444',         // Muted text
        },
        // Accent color - Elegant Blue
        accent: {
          DEFAULT: '#3b82f6',       // Primary accent
          hover: '#2563eb',         // Hover state
          active: '#1d4ed8',        // Active state
          subtle: '#60a5fa',        // Subtle accent
        },
        // Functional colors
        success: {
          DEFAULT: '#10b981',       // Success green
          subtle: '#34d399',        // Subtle success
        },
        warning: {
          DEFAULT: '#f59e0b',       // Warning amber
          subtle: '#fbbf24',        // Subtle warning
        },
        error: {
          DEFAULT: '#ef4444',       // Error red
          subtle: '#f87171',        // Subtle error
        },
        info: {
          DEFAULT: '#3b82f6',       // Info blue
          subtle: '#60a5fa',        // Subtle info
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Monaco', 'Consolas', 'monospace'],
      },
      fontSize: {
        'xs': ['0.75rem', { lineHeight: '1rem' }],
        'sm': ['0.875rem', { lineHeight: '1.25rem' }],
        'base': ['1rem', { lineHeight: '1.5rem' }],
        'lg': ['1.125rem', { lineHeight: '1.75rem' }],
        'xl': ['1.25rem', { lineHeight: '1.75rem' }],
        '2xl': ['1.5rem', { lineHeight: '2rem' }],
        '3xl': ['1.875rem', { lineHeight: '2.25rem' }],
        '4xl': ['2.25rem', { lineHeight: '2.5rem' }],
      },
      spacing: {
        '18': '4.5rem',
        '22': '5.5rem',
        '88': '22rem',
        '92': '23rem',
        '96': '24rem',
      },
      borderRadius: {
        'sm': '4px',
        'DEFAULT': '6px',
        'md': '8px',
        'lg': '12px',
        'xl': '16px',
      },
      boxShadow: {
        'subtle': '0 1px 2px 0 rgba(0, 0, 0, 0.3)',
        'medium': '0 4px 6px -1px rgba(0, 0, 0, 0.4)',
        'elevated': '0 10px 15px -3px rgba(0, 0, 0, 0.5)',
        'glow': '0 0 20px rgba(59, 130, 246, 0.1)',
      },
      animation: {
        'fade-in': 'fadeIn 0.2s ease-in-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'slide-down': 'slideDown 0.3s ease-out',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        slideDown: {
          '0%': { transform: 'translateY(-10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
