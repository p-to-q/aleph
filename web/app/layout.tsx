import './global.css'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Aleph',
  description:
    'For any output, find a short prompt that regenerates it — an upper bound on the shortest, under a fixed local model.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
