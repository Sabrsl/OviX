/**
 * Reusable Button Component
 * 
 * Consistent button styling across the application.
 * Matches the style used in PublicationDetail page.
 */

import { ReactNode, useEffect, forwardRef } from 'react'

type ButtonVariant = 'primary' | 'neutral' | 'danger' | 'success'

interface ButtonProps {
  children: ReactNode
  onClick?: () => void
  disabled?: boolean
  variant?: ButtonVariant
  type?: 'button' | 'submit' | 'reset'
  className?: string
  style?: React.CSSProperties
}

const colors = {
  bgPanel: '#121212',
  bgInput: '#1e1e1e',
  border: '#3a3a3a',
  borderHover: '#4a4a4a',
  textPrimary: '#f5f5f5',
  textSecondary: '#e0e0e0',
  textWhite: '#ffffff',

  error: '#dc2626',
  errorSoft: 'rgba(220, 38, 38, 0.12)',
  errorSoftHover: 'rgba(220, 38, 38, 0.2)',
  errorBorder: 'rgba(220, 38, 38, 0.35)',
  errorBorderHover: 'rgba(220, 38, 38, 0.5)',

  success: '#059669',
  successSoft: 'rgba(5, 150, 105, 0.12)',
  successSoftHover: 'rgba(5, 150, 105, 0.2)',
  successBorder: 'rgba(5, 150, 105, 0.35)',
  successBorderHover: 'rgba(5, 150, 105, 0.5)',

  focusRing: 'rgba(255, 255, 255, 0.25)',
}

const baseStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '6px',
  padding: '8px 12px',
  borderRadius: '6px',
  fontSize: '12px',
  fontWeight: 500,
  border: 'none',
  cursor: 'pointer',
  transition: 'opacity 0.15s ease, transform 0.05s ease, background-color 0.15s ease, border-color 0.15s ease',
}

// Corrigé : primary utilise maintenant colors.bgInput / colors.border
// au lieu de valeurs codées en dur trop proches du hover
const variantStyles: Record<ButtonVariant, React.CSSProperties> = {
  primary: {
    backgroundColor: colors.bgInput,
    color: colors.textSecondary,
    border: `1px solid ${colors.border}`,
  },
  neutral: {
    backgroundColor: colors.bgPanel,
    color: colors.textPrimary,
    border: `1px solid ${colors.border}`,
  },
  danger: {
    backgroundColor: colors.errorSoft,
    color: '#fca5a5',
    border: `1px solid ${colors.errorBorder}`,
  },
  success: {
    backgroundColor: colors.successSoft,
    color: colors.success,
    border: `1px solid ${colors.successBorder}`,
  },
}

// Hover states volontairement discrets : léger éclaircissement du fond et
// de la bordure, sans changement brutal de couleur (évite l'effet "flash").
const hoverStyles: Record<ButtonVariant, { backgroundColor: string; color?: string; borderColor: string }> = {
  primary: {
    backgroundColor: '#242424',
    borderColor: '#333333',
  },
  neutral: {
    backgroundColor: '#161616',
    borderColor: '#333333',
  },
  danger: {
    backgroundColor: colors.errorSoftHover,
    borderColor: colors.errorBorderHover,
  },
  success: {
    backgroundColor: colors.successSoftHover,
    borderColor: colors.successBorderHover,
  },
}

const disabledStyle: React.CSSProperties = {
  opacity: 0.55,
  cursor: 'not-allowed',
}

// Injection unique du CSS global, une seule fois pour toute l'app
// (au lieu d'un <style> réinjecté à chaque render de chaque bouton)
let stylesInjected = false
function ensureGlobalStyles() {
  if (stylesInjected || typeof document === 'undefined') return
  stylesInjected = true

  const css = (Object.keys(hoverStyles) as ButtonVariant[])
    .map((variant) => {
      const hover = hoverStyles[variant]
      return `
        .ovix-button-${variant}:hover:not(:disabled) {
          background-color: ${hover.backgroundColor} !important;
          ${hover.color ? `color: ${hover.color} !important;` : ''}
          border-color: ${hover.borderColor} !important;
        }
        .ovix-button-${variant}:focus-visible {
          box-shadow: 0 0 0 3px ${colors.focusRing};
        }
      `
    })
    .join('\n')

  const styleEl = document.createElement('style')
  styleEl.setAttribute('data-ovix-button-styles', 'true')
  styleEl.textContent = css
  document.head.appendChild(styleEl)
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  function Button(
    {
      children,
      onClick,
      disabled = false,
      variant = 'neutral',
      type = 'button',
      className = '',
      style: customStyle,
    }: ButtonProps,
    ref
  ) {
    useEffect(() => {
      ensureGlobalStyles()
    }, [])

    const getStyle = (): React.CSSProperties => {
      let style = { ...baseStyle, ...variantStyles[variant] }

      if (disabled) {
        style = { ...style, ...disabledStyle }
      }

      if (customStyle) {
        style = { ...style, ...customStyle }
      }

      return style
    }

    return (
      <button
        ref={ref}
        type={type}
        onClick={onClick}
        disabled={disabled}
        className={`ovix-button-${variant} ${className}`}
        style={getStyle()}
      >
        {children}
      </button>
    )
  }
)

Button.displayName = 'Button'

export default Button