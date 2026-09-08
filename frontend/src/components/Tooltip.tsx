import { useState, useRef, useEffect, useId, useCallback } from 'react'
import { createPortal } from 'react-dom'

interface TooltipProps {
  children: React.ReactNode
  content: React.ReactNode
  position?: 'top' | 'bottom' | 'left' | 'right'
  delay?: number
  className?: string
  disabled?: boolean
}

const ARROW_SIZE = 4

export default function Tooltip({
  children,
  content,
  position = 'top',
  delay = 200,
  className = '',
  disabled = false,
}: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false)
  const [resolvedPosition, setResolvedPosition] = useState(position)
  const showTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)
  const hideTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)
  const containerRef = useRef<HTMLSpanElement>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)
  const tooltipId = useId()

  const clearTimers = () => {
    if (showTimeout.current) clearTimeout(showTimeout.current)
    if (hideTimeout.current) clearTimeout(hideTimeout.current)
  }

  const show = useCallback(() => {
    if (disabled || !content) return
    clearTimers()
    showTimeout.current = setTimeout(() => setIsVisible(true), delay)
  }, [disabled, content, delay])

  const hide = useCallback(() => {
    clearTimers()
    hideTimeout.current = setTimeout(() => setIsVisible(false), 100)
  }, [])

  const hideImmediately = useCallback(() => {
    clearTimers()
    setIsVisible(false)
  }, [])

  // Cleanup on unmount to avoid state updates after unmount
  useEffect(() => clearTimers, [])

  // Escape closes; only when this tooltip is actually open
  useEffect(() => {
    if (!isVisible) return
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') hideImmediately()
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [isVisible, hideImmediately])

  // Calculate position for fixed positioning with Portal
  useEffect(() => {
    if (!isVisible) return
    const container = containerRef.current
    const tooltip = tooltipRef.current
    if (!container || !tooltip) {
      setResolvedPosition(position)
      return
    }

    const containerRect = container.getBoundingClientRect()
    const tooltipRect = tooltip.getBoundingClientRect()
    const margin = 8
    let next = position

    if (position === 'top' && containerRect.top - tooltipRect.height - margin < 0) {
      next = 'bottom'
    } else if (
      position === 'bottom' &&
      containerRect.bottom + tooltipRect.height + margin > window.innerHeight
    ) {
      next = 'top'
    } else if (position === 'left' && containerRect.left - tooltipRect.width - margin < 0) {
      next = 'right'
    } else if (
      position === 'right' &&
      containerRect.right + tooltipRect.width + margin > window.innerWidth
    ) {
      next = 'left'
    }

    setResolvedPosition(next)

    // Calculate fixed position based on container rect
    const positionStyles: Record<string, React.CSSProperties> = {
      top: {
        left: `${containerRect.left + containerRect.width / 2}px`,
        top: `${containerRect.top - tooltipRect.height - ARROW_SIZE - 3}px`,
        transform: 'translateX(-50%)',
      },
      bottom: {
        left: `${containerRect.left + containerRect.width / 2}px`,
        top: `${containerRect.bottom + ARROW_SIZE + 3}px`,
        transform: 'translateX(-50%)',
      },
      left: {
        left: `${containerRect.left - tooltipRect.width - ARROW_SIZE - 3}px`,
        top: `${containerRect.top + containerRect.height / 2}px`,
        transform: 'translateY(-50%)',
      },
      right: {
        left: `${containerRect.right + ARROW_SIZE + 3}px`,
        top: `${containerRect.top + containerRect.height / 2}px`,
        transform: 'translateY(-50%)',
      },
    }

    Object.assign(tooltip.style, positionStyles[next])

    // Calculate arrow position for fixed positioning
    const arrow = tooltip.querySelector('[aria-hidden="true"]') as HTMLElement
    if (arrow) {
      const arrowStyles: Record<string, React.CSSProperties> = {
        top: {
          left: `${containerRect.left + containerRect.width / 2}px`,
          top: `${containerRect.top - ARROW_SIZE}px`,
          transform: 'translateX(-50%) rotate(45deg)',
        },
        bottom: {
          left: `${containerRect.left + containerRect.width / 2}px`,
          top: `${containerRect.bottom - ARROW_SIZE}px`,
          transform: 'translateX(-50%) rotate(45deg)',
        },
        left: {
          left: `${containerRect.left - ARROW_SIZE}px`,
          top: `${containerRect.top + containerRect.height / 2}px`,
          transform: 'translateY(-50%) rotate(45deg)',
        },
        right: {
          left: `${containerRect.right - ARROW_SIZE}px`,
          top: `${containerRect.top + containerRect.height / 2}px`,
          transform: 'translateY(-50%) rotate(45deg)',
        },
      }
      Object.assign(arrow.style, arrowStyles[next])
    }
  }, [isVisible, position])

  return (
    <span
      ref={containerRef}
      className={`tooltip-container ${className}`}
      style={{ position: 'relative', display: 'inline-block' }}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      <span
        aria-describedby={isVisible ? tooltipId : undefined}
        style={{ display: 'inline-block', cursor: 'inherit' }}
      >
        {children}
      </span>

      {isVisible && content && createPortal(
        <div
          ref={tooltipRef}
          id={tooltipId}
          role="tooltip"
          className="tooltip-bubble"
          style={{
            position: 'fixed',
            zIndex: 1000,
            pointerEvents: 'none',
            backgroundColor: 'var(--tooltip-bg, #1a1a1a)',
            color: 'var(--tooltip-fg, #f5f5f5)',
            padding: '3px 6px',
            borderRadius: '4px',
            fontSize: '11px',
            fontWeight: 500,
            lineHeight: 1.3,
            maxWidth: '160px',
            width: 'max-content',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.25), 0 0 0 1px rgba(255, 255, 255, 0.06)',
            whiteSpace: 'normal',
          }}
        >
          <span
            aria-hidden="true"
            style={{
              position: 'absolute',
              width: ARROW_SIZE * 2,
              height: ARROW_SIZE * 2,
              backgroundColor: 'var(--tooltip-bg, #1a1a1a)',
            }}
          />
          {content}
        </div>,
        document.body
      )}

      <style>{`
        .tooltip-bubble {
          animation: tooltipFadeIn 0.12s ease-out;
        }
        @keyframes tooltipFadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @media (prefers-reduced-motion: reduce) {
          .tooltip-bubble {
            animation: none;
          }
        }
      `}</style>
    </span>
  )
}