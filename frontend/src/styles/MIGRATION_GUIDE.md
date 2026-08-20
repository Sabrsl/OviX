# Guide de Migration - Styles Inline vers CSS Global

Ce guide vous aide à migrer les styles inline (`style={{ ... }}`) vers les classes CSS centralisées du fichier `global.css`.

## 🎯 Pourquoi migrer ?

- **Maintenabilité** : Styles centralisés et réutilisables
- **Performance** : Meilleure optimisation du navigateur
- **Consistance** : Design system uniforme
- **Accessibilité** : Classes sémantiques plus claires

## 📋 Équivalences Styles Inline → Classes CSS

### Layout & Flexbox

**Inline:**
```tsx
<div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
```

**CSS Global:**
```tsx
<div className="flex items-center gap-sm">
```

**Inline:**
```tsx
<div style={{ display: 'flex', justifyContent: 'space-between' }}>
```

**CSS Global:**
```tsx
<div className="flex justify-between">
```

**Inline:**
```tsx
<div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)' }}>
```

**CSS Global:**
```tsx
<div className="grid grid-cols-3">
```

### Couleurs de fond

**Inline:**
```tsx
<div style={{ backgroundColor: '#0a0a0a' }}>
```

**CSS Global:**
```tsx
<div style={{ backgroundColor: 'var(--bg-primary)' }}>
```

### Couleurs de texte

**Inline:**
```tsx
<span style={{ color: '#f5f5f5' }}>
```

**CSS Global:**
```tsx
<span className="text-primary">
```

**Inline:**
```tsx
<span style={{ color: '#a0a0a0' }}>
```

**CSS Global:**
```tsx
<span className="text-tertiary">
```

### Boutons

**Inline:**
```tsx
<button style={{
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  padding: '7px 12px',
  backgroundColor: '#3b82f6',
  color: 'white',
  border: 'none',
  borderRadius: '6px',
  cursor: 'pointer',
  fontSize: '12px',
  fontWeight: 500
}}>
```

**CSS Global:**
```tsx
<button className="btn btn-primary btn-sm">
```

**Inline:**
```tsx
<button style={{
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  padding: '7px 12px',
  backgroundColor: 'transparent',
  color: '#a0a0a0',
  border: 'none',
  borderRadius: '6px',
  cursor: 'pointer'
}}>
```

**CSS Global:**
```tsx
<button className="btn btn-ghost btn-sm">
```

### Cards

**Inline:**
```tsx
<div style={{
  padding: '16px 18px',
  backgroundColor: '#1a1a1a',
  border: '1px solid #2a2a2a',
  borderRadius: '10px'
}}>
```

**CSS Global:**
```tsx
<div className="card">
```

**Inline (Interactive):**
```tsx
<div style={{
  padding: '16px 18px',
  backgroundColor: '#1a1a1a',
  border: '1px solid #2a2a2a',
  borderRadius: '10px',
  cursor: 'pointer',
  transition: 'border-color 0.15s, background-color 0.15s'
}}
onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#3a3a3a' }}
onMouseLeave={(e) => { e.currentTarget.style.borderColor = '#2a2a2a' }}
>
```

**CSS Global:**
```tsx
<div className="card-interactive">
```

### Inputs

**Inline:**
```tsx
<input style={{
  width: '100%',
  padding: '12px',
  backgroundColor: '#0a0a0a',
  border: '1px solid #2a2a2a',
  borderRadius: '6px',
  color: '#f5f5f5',
  fontSize: '14px'
}}
/>
```

**CSS Global:**
```tsx
<input className="input" />
```

### Badges

**Inline:**
```tsx
<span style={{
  padding: '2px 7px',
  backgroundColor: '#10b98118',
  color: '#10b981',
  fontSize: '10px',
  fontWeight: 600,
  borderRadius: '4px',
  border: '1px solid #10b98135'
}}>
```

**CSS Global:**
```tsx
<span className="badge badge-success">
```

### Alerts

**Inline:**
```tsx
<div style={{
  padding: '10px 14px',
  backgroundColor: 'rgba(239, 68, 68, 0.08)',
  border: '1px solid rgba(239, 68, 68, 0.25)',
  borderRadius: '8px',
  color: '#ef4444',
  fontSize: '12.5px',
  display: 'flex',
  alignItems: 'center',
  gap: '8px'
}}>
```

**CSS Global:**
```tsx
<div className="alert alert-error">
```

### Typography

**Inline:**
```tsx
<h1 style={{ fontSize: '24px', fontWeight: 600, color: '#f5f5f5' }}>
```

**CSS Global:**
```tsx
<h1 className="text-2xl font-semibold text-primary">
```

**Inline:**
```tsx
<p style={{ fontSize: '12px', color: '#8a8a8a' }}>
```

**CSS Global:**
```tsx
<p className="text-sm text-tertiary">
```

### Spacing

**Inline:**
```tsx
<div style={{ padding: '20px' }}>
```

**CSS Global:**
```tsx
<div className="p-xl">
```

**Inline:**
```tsx
<div style={{ margin: '24px 0' }}>
```

**CSS Global:**
```tsx
<div className="my-2xl">
```

### Icons

**Inline:**
```tsx
<div style={{
  width: '34px',
  height: '34px',
  borderRadius: '8px',
  backgroundColor: '#3b82f620',
  border: '1px solid #3b82f640',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center'
}}>
```

**CSS Global:**
```tsx
<div className="icon-wrapper icon-wrapper-blue" style={{ width: '34px', height: '34px' }}>
```

### Status indicators

**Inline:**
```tsx
<div style={{
  width: '8px',
  height: '8px',
  backgroundColor: '#10b981',
  borderRadius: '50%',
  animation: 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite'
}}
/>
```

**CSS Global:**
```tsx
<div className="status-dot status-dot-online" />
```

## 🚀 Exemples de Migration Complets

### Exemple 1: Header de page

**Avant (Inline):**
```tsx
<div style={{
  display: 'flex',
  alignItems: 'flex-start',
  justifyContent: 'space-between',
  gap: '16px',
  marginBottom: '20px',
  flexWrap: 'wrap'
}}>
  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
    <div style={{
      width: '34px',
      height: '34px',
      borderRadius: '8px',
      backgroundColor: '#3b82f620',
      border: '1px solid #3b82f640',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center'
    }}>
      <Icon style={{ width: '17px', height: '17px', color: '#3b82f6' }} />
    </div>
    <div>
      <h1 style={{ fontSize: '17px', fontWeight: 600, color: '#e0e0e0' }}>
        Titre
      </h1>
      <p style={{ fontSize: '12px', color: '#8a8a8a', marginTop: '2px' }}>
        Description
      </p>
    </div>
  </div>
</div>
```

**Après (CSS Global):**
```tsx
<div className="page-header">
  <div className="page-header-title">
    <div className="page-header-icon">
      <Icon className="icon-md" style={{ color: 'var(--accent-blue)' }} />
    </div>
    <div>
      <h1 className="text-lg font-semibold text-secondary">Titre</h1>
      <p className="text-sm text-tertiary mt-xs">Description</p>
    </div>
  </div>
</div>
```

### Exemple 2: Filtres

**Avant (Inline):**
```tsx
<div style={{
  display: 'flex',
  gap: '6px',
  marginBottom: '20px',
  padding: '6px',
  backgroundColor: '#1a1a1a',
  borderRadius: '9px',
  border: '1px solid #2a2a2a',
  flexWrap: 'wrap'
}}>
  <button
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '6px',
      padding: '7px 13px',
      backgroundColor: isActive ? '#3b82f6' : 'transparent',
      color: isActive ? '#ffffff' : '#a0a0a0',
      border: 'none',
      borderRadius: '6px',
      cursor: 'pointer',
      fontSize: '12.5px',
      fontWeight: 500
    }}
  >
    Label
  </button>
</div>
```

**Après (CSS Global):**
```tsx
<div className="filter-tabs">
  <button className={`filter-tab ${isActive ? 'active' : ''}`}>
    Label
  </button>
</div>
```

### Exemple 3: Item Card

**Avant (Inline):**
```tsx
<div
  style={{
    padding: '16px 18px',
    backgroundColor: '#1a1a1a',
    border: '1px solid #2a2a2a',
    borderRadius: '10px',
    cursor: 'pointer',
    transition: 'border-color 0.15s, background-color 0.15s',
    width: '100%',
    maxWidth: '100%',
    boxSizing: 'border-box',
    overflow: 'hidden'
  }}
  onClick={() => setSelectedItem(item)}
  onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#3a3a3a' }}
  onMouseLeave={(e) => { e.currentTarget.style.borderColor = '#2a2a2a' }}
>
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px' }}>
    <div style={{ flex: 1, minWidth: 0 }}>
      <h3 style={{ fontSize: '13.5px', fontWeight: 600, color: '#e0e0e0' }}>
        Title
      </h3>
    </div>
  </div>
</div>
```

**Après (CSS Global):**
```tsx
<div
  className="item-card"
  onClick={() => setSelectedItem(item)}
>
  <div className="item-card-header">
    <div className="item-card-title">
      <h3 className="text-secondary">Title</h3>
    </div>
  </div>
</div>
```

## 📝 Checklist de Migration

Pour chaque composant:

1. **Identifier les patterns récurrents** (cards, buttons, headers, etc.)
2. **Remplacer les styles inline par les classes CSS** correspondantes
3. **Utiliser les variables CSS** pour les couleurs personnalisées
4. **Supprimer les handlers onMouseEnter/onMouseLeave** si les classes CSS gèrent les hover states
5. **Tester le rendu visuel** pour s'assurer de la consistance

## 🔧 Variables CSS Disponibles

```css
--bg-primary: #0a0a0a        /* Fond principal */
--bg-secondary: #111111      /* Fond secondaire */
--bg-tertiary: #161616       /* Fond tertiaire */
--bg-elevated: #1a1a1a       /* Fond élevé */
--bg-hover: #2a2a2a          /* Fond au hover */

--text-primary: #f5f5f5      /* Texte principal */
--text-secondary: #e0e0e0    /* Texte secondaire */
--text-tertiary: #a0a0a0     /* Texte tertiaire */
--text-muted: #666666        /* Texte muted */

--accent-blue: #3b82f6       /* Accent bleu */
--accent-green: #10b981      /* Accent vert */
--accent-red: #ef4444        /* Accent rouge */
--accent-yellow: #f59e0b     /* Accent jaune */
--accent-purple: #a78bfa     /* Accent violet */
--accent-cyan: #38bdf8       /* Accent cyan */

--border-color: #2a2a2a      /* Bordure */
--border-hover: #3a3a3a      /* Bordure au hover */
--border-focus: #3b82f6      /* Bordure au focus */
```

## 💡 Bonnes Pratiques

1. **Privilégier les classes CSS** sur les styles inline
2. **Utiliser les variables CSS** pour la consistance
3. **Composer les classes** plutôt que créer des styles custom
4. **Garder les styles inline** uniquement pour les valeurs dynamiques (calculées en JS)
5. **Utiliser les classes utilitaires** pour les cas simples (spacing, display, etc.)

## 🎨 Classes Spécifiques par Composant

Le fichier `global.css` inclut des classes spécifiques pour:

- **Headers**: `.page-header`, `.page-header-title`, `.page-header-icon`
- **Filtres**: `.filter-tabs`, `.filter-tab`, `.filter-tab-count`
- **Cards**: `.card`, `.card-elevated`, `.card-interactive`
- **Items**: `.item-grid`, `.item-card`, `.item-card-header`
- **Empty states**: `.empty-state`, `.empty-state-icon`
- **Modals**: `.modal-overlay`, `.modal-content`, `.modal-header`

Ces classes encapsulent des patterns complexes et réduisent le besoin de styles inline.