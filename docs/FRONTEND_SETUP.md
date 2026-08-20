# OVIX Frontend - Setup Guide

## Overview

The OVIX frontend is a modern React + TypeScript application with a premium dark aesthetic, built with Vite, Tailwind CSS, and React Router.

## Design System

### Color Palette (Dark Premium)

The interface is built around a sophisticated dark theme:

- **Backgrounds**: Deep blacks and anthracite (#0a0a0a, #111111, #161616)
- **Text**: Off-white with clear hierarchy (#ffffff, #f5f5f5, #a0a0a0)
- **Accent**: Elegant blue (#3b82f6) used sparingly
- **Functional colors**: Subtle success, warning, and error indicators

### Typography

- **Primary**: Inter (clean, modern sans-serif)
- **Monospace**: JetBrains Mono (for code, logs, URLs)
- **Clear hierarchy**: Page titles → Section titles → Descriptions → Data → Metadata

### Visual Principles

- Minimal decoration, maximum quality
- Strong visual hierarchy
- Generous spacing
- Subtle animations (fast, fluid, purposeful)
- Premium, professional aesthetic inspired by Linear/Vercel

## Installation

### Prerequisites

- Node.js 18+ and npm
- Python 3.10+ (for backend API)
- FastAPI backend running on port 8001

### Installation Steps

1. **Navigate to frontend directory**:
```bash
cd frontend
```

2. **Install dependencies**:
```bash
npm install
```

Or using PowerShell:
```powershell
Push-Location "path\to\frontend"
npm install
Pop-Location
```

3. **Start development server**:
```bash
npm run dev
```

The application will be available at `http://localhost:3000` (or another port if 3000 is in use).

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   └── Layout.tsx          # Main layout with sidebar and top bar
│   ├── pages/
│   │   ├── Dashboard.tsx       # Main dashboard
│   │   ├── AnalysisNew.tsx    # New analysis form
│   │   ├── AnalysisResults.tsx # Analysis results
│   │   ├── PublicationPending.tsx # Pending publications
│   │   ├── PublicationHistory.tsx # Publication history
│   │   ├── SystemLogs.tsx      # System logs
│   │   ├── SystemScheduler.tsx # Scheduler controls
│   │   ├── SystemKillSwitch.tsx # Kill switch controls
│   │   └── Settings.tsx       # Settings page
│   ├── lib/
│   │   └── utils.ts           # Utility functions (cn helper)
│   ├── App.tsx                # Main app with routing
│   ├── main.tsx               # Entry point
│   └── index.css              # Global styles and Tailwind
├── index.html                 # HTML template
├── package.json              # Dependencies
├── tsconfig.json             # TypeScript config
├── tailwind.config.js        # Tailwind configuration
├── vite.config.ts            # Vite configuration
└── postcss.config.js         # PostCSS configuration
```

## Features Implemented

### Layout
- **Sidebar**: Compact, elegant navigation with expandable sections
- **Top Bar**: Minimal status indicators (Wikipedia connection, OVIX status, Kill Switch)
- **Main Content**: Scrollable content area with smooth animations

### Pages
- **Dashboard**: System overview, statistics, recent activity
- **Analysis**: New analysis form and results view (placeholders)
- **Publication**: Pending approvals and history (placeholders)
- **System**: Logs, scheduler, and kill switch controls
- **Settings**: Configuration page (placeholder)

### Design Components
- **Cards**: Elevated surfaces with subtle borders
- **Buttons**: Primary (accent), secondary (neutral), ghost (subtle), danger (error)
- **Badges**: Status indicators with functional colors
- **Tables**: Clean, professional data tables with hover states
- **Inputs**: Styled form inputs with focus states

### Animations
- Fade-in for page transitions
- Slide-up for content appearance
- Pulse for status indicators
- Smooth hover effects

## API Integration

The frontend is configured to proxy API requests to the FastAPI backend:

```typescript
// vite.config.ts
server: {
  port: 3000,
  proxy: {
    '/api': {
      target: 'http://127.0.0.1:8001',
      changeOrigin: true,
    }
  }
}
```

API calls can be made using axios:

```typescript
import axios from 'axios'

const response = await axios.get('/api/health')
```

## Scripts de Démarrage

Le projet inclut des scripts pour simplifier le démarrage:

### start-ovix.ps1 (PowerShell)
Script principal qui lance:
- L'API FastAPI (backend/api/main_standalone.py)
- Le frontend React (npm run dev)
- Gestion automatique des processus existants
- Arrêt propre sur Ctrl+C

### start-ovix.bat (Batch)
Version Windows batch du script principal avec les mêmes fonctionnalités.

### restart_api.ps1
Script pour redémarrer uniquement l'API FastAPI avec tests de santé.

### Pourquoi utiliser Push-Location/Pop-Location?
Les commandes npm doivent être exécutées dans le bon répertoire. `Push-Location` change temporairement le répertoire de travail pour exécuter la commande, puis `Pop-Location` revient au répertoire original. C'est plus propre que `cd && cd ..` dans PowerShell.

## Starting the Application

### Démarrage Complet (Backend + Frontend)

**Commande unique recommandée:**

**Windows PowerShell:**
```powershell
.\start-ovix.ps1
```

**Windows Batch:**
```cmd
start-ovix.bat
```

Cette commande lance simultanément:
- L'API FastAPI sur http://localhost:8001
- Le frontend React sur http://localhost:3000

### Démarrage Individuel

**Backend API uniquement:**
```powershell
powershell -ExecutionPolicy Bypass -File restart_api.ps1
```

**Frontend uniquement:**
```bash
cd frontend
npm run dev
```

Access at: `http://localhost:3000`

### Production Build

```bash
cd frontend
npm run build
```

Built files will be in `dist/` directory.

### Preview Production Build

```bash
cd frontend
npm run preview
```

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint

## Browser Support

- Modern browsers (Chrome, Firefox, Safari, Edge)
- Responsive design (desktop, laptop, tablet)

## Customization

### Colors

Edit `tailwind.config.js` to customize the color palette:

```javascript
colors: {
  accent: {
    DEFAULT: '#3b82f6',  // Change accent color
    // ...
  }
}
```

### Fonts

The application uses Google Fonts (Inter and JetBrains Mono). To change fonts, update:
1. `index.html` - Google Fonts link
2. `tailwind.config.js` - fontFamily configuration

### Layout

Modify `src/components/Layout.tsx` to adjust sidebar, top bar, or content area.

## Future Enhancements

### Planned Features
- Real Wikipedia API integration
- Analysis form with article selection
- Results table with diff viewer
- Publication approval workflow
- Live logs viewer
- Scheduler controls
- Settings management
- Wikipedia diff viewer with syntax highlighting

### API Integration Points
- Authentication (Wikipedia login)
- Article retrieval and search
- Analysis job management
- Publication validation and approval
- System status monitoring
- Logs and history retrieval

## Troubleshooting

### Port Already in Use
If port 3000 is in use, modify `vite.config.ts`:
```typescript
server: {
  port: 3001,  // Change port
  // ...
}
```

### Dependencies Issues
Clear npm cache and reinstall:
```bash
npm cache clean --force
npm install
```

### TypeScript Errors
Ensure all dependencies are installed:
```bash
npm install
```

## Design Philosophy

The OVIX frontend follows these principles:

1. **Less decoration, more quality** - Focus on precision and clarity
2. **Strong visual hierarchy** - Clear information structure
3. **Dark theme as foundation** - Professional, premium aesthetic
4. **Accent as emphasis** - Color used purposefully, not abundantly
5. **Rapid interactions** - Fast, fluid animations that enhance UX
6. **Professional first** - Serious, tool-focused design
7. **Dense but readable** - Information-rich without overwhelming

The design communicates: Precision, Control, Reliability, Automation, Security.
