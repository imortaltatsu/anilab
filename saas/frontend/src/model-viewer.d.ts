import type { CSSProperties, DetailedHTMLProps, HTMLAttributes } from 'react'

declare module 'react' {
  namespace JSX {
    interface IntrinsicElements {
      'model-viewer': DetailedHTMLProps<HTMLAttributes<HTMLElement>, HTMLElement> & {
        src?: string
        alt?: string
        poster?: string
        ar?: boolean
        'camera-controls'?: boolean
        'touch-action'?: string
        'auto-rotate'?: boolean
        'shadow-intensity'?: string | number
        exposure?: string | number
        'animation-name'?: string
        autoplay?: boolean
        'environment-image'?: string
        style?: CSSProperties
      }
    }
  }
}

export {}
