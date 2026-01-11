/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  safelist: [
    // Gradient classes for login page
    'from-blue-500/10',
    'to-indigo-500/10',
    'from-rose-500/10',
    'to-pink-500/10',
    'from-amber-500/10',
    'to-orange-500/10',
    'from-primary/20',
    'to-accent/20',
    'from-emerald-200/30',
    'to-teal-200/30',
    'bg-secondary/50',
    // Ensure base gradient utilities are included
    {
      pattern: /^(from|via|to)-(blue|indigo|rose|pink|amber|orange|emerald|teal|primary|accent|secondary)-(50|100|200|500)\/(10|20|30|40|50)$/,
    },
  ],
  theme: {
    extend: {
      colors: {
        background: 'var(--background)',
        foreground: 'var(--foreground)',
        card: {
          DEFAULT: 'var(--card)',
          foreground: 'var(--card-foreground)',
        },
        popover: {
          DEFAULT: 'var(--popover)',
          foreground: 'var(--popover-foreground)',
        },
        primary: {
          DEFAULT: 'var(--primary)',
          foreground: 'var(--primary-foreground)',
        },
        secondary: {
          DEFAULT: 'var(--secondary)',
          foreground: 'var(--secondary-foreground)',
        },
        muted: {
          DEFAULT: 'var(--muted)',
          foreground: 'var(--muted-foreground)',
        },
        accent: {
          DEFAULT: 'var(--accent)',
          foreground: 'var(--accent-foreground)',
        },
        destructive: {
          DEFAULT: 'var(--destructive)',
          foreground: 'var(--destructive-foreground)',
        },
        border: 'var(--border)',
        input: 'var(--input)',
        'input-background': 'var(--input-background)',
        ring: 'var(--ring)',
        // Sidebar palette
        sidebar: 'var(--sidebar)',
        'sidebar-foreground': 'var(--sidebar-foreground)',
        'sidebar-primary': 'var(--sidebar-primary)',
        'sidebar-primary-foreground': 'var(--sidebar-primary-foreground)',
        'sidebar-accent': 'var(--sidebar-accent)',
        'sidebar-accent-foreground': 'var(--sidebar-accent-foreground)',
        'sidebar-border': 'var(--sidebar-border)',
        'sidebar-ring': 'var(--sidebar-ring)',
        // Tailwind default colors for gradients
        emerald: {
          50: 'var(--color-emerald-50)',
          200: 'var(--color-emerald-200)',
        },
        teal: {
          50: 'var(--color-teal-50)',
          200: 'var(--color-teal-200)',
        },
        cyan: {
          50: 'var(--color-cyan-50)',
        },
        green: {
          50: 'var(--color-green-50)',
        },
        slate: {
          50: 'var(--color-slate-50)',
          100: 'var(--color-slate-100)',
        },
        gray: {
          100: 'var(--color-gray-100)',
        },
        blue: {
          500: 'var(--color-blue-500)',
        },
        indigo: {
          500: 'var(--color-indigo-500)',
        },
        rose: {
          500: 'var(--color-rose-500)',
        },
        pink: {
          500: 'var(--color-pink-500)',
        },
        purple: {
          500: 'var(--color-purple-500)',
        },
        amber: {
          500: 'var(--color-amber-500)',
        },
        orange: {
          500: 'var(--color-orange-500)',
        },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
    },
  },
  plugins: [],
}
