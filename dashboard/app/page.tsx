import Link from 'next/link'

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center p-8">
      <div className="text-center max-w-2xl">
        <h1 className="text-5xl font-bold mb-4">
          🌐 TranslateAPI
        </h1>
        <p className="text-xl text-gray-400 mb-8">
          Fast, affordable translation API for developers
        </p>
        <div className="flex gap-4 justify-center">
          <Link
            href="/login"
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg font-semibold transition"
          >
            Login
          </Link>
          <Link
            href="/signup"
            className="px-6 py-3 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 rounded-lg font-semibold transition"
          >
            Sign Up
          </Link>
        </div>
      </div>
    </main>
  )
}
