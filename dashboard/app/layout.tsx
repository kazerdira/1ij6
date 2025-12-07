import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'TranslateAPI - Dashboard',
  description: 'Manage your TranslateAPI account, API keys, and usage',
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
