import './global.css'
import type { Metadata } from 'next'
import { Analytics } from '@vercel/analytics/next'

const description =
  'For any output, find a short prompt that regenerates it — an upper bound on the shortest, under a fixed local model.'

export const metadata: Metadata = {
  metadataBase: new URL('https://aleph.ptoq.io'),
  title: 'Aleph',
  description,
  alternates: {
    canonical: '/',
  },
  icons: {
    icon: '/aleph-logo.png',
    apple: '/aleph-logo.png',
  },
  openGraph: {
    title: 'Aleph',
    description,
    url: '/',
    siteName: 'Aleph',
    type: 'website',
    images: [
      {
        url: '/aleph-logo.png',
        width: 820,
        height: 820,
        alt: 'Aleph',
      },
    ],
  },
  twitter: {
    card: 'summary',
    title: 'Aleph',
    description,
    images: ['/aleph-logo.png'],
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>
        {children}
        <Analytics />
      </body>
    </html>
  )
}
