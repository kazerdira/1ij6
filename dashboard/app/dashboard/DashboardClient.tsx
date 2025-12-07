'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'

interface DashboardProps {
  user: any
  profile: any
  apiKeys: any[]
  monthlyUsage: any
  tierLimits: any
  recentUsage: any[]
}

export default function DashboardClient({
  user,
  profile,
  apiKeys,
  monthlyUsage,
  tierLimits,
  recentUsage,
}: DashboardProps) {
  const [keys, setKeys] = useState(apiKeys)
  const [newKey, setNewKey] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [keyName, setKeyName] = useState('Default')
  const router = useRouter()
  const supabase = createClient()

  const requestCount = monthlyUsage?.request_count || 0
  const requestLimit = tierLimits?.requests_per_month || 1000
  const usagePercent = Math.min((requestCount / requestLimit) * 100, 100)

  const handleGenerateKey = async () => {
    setLoading(true)
    try {
      const { data, error } = await supabase.rpc('generate_api_key', {
        key_name: keyName,
      })

      if (error) throw error

      if (data && data[0]) {
        setNewKey(data[0].api_key)
        router.refresh()
      }
    } catch (err) {
      console.error('Failed to generate key:', err)
      alert('Failed to generate API key')
    } finally {
      setLoading(false)
    }
  }

  const handleRevokeKey = async (keyId: string) => {
    if (!confirm('Are you sure you want to revoke this API key?')) return

    try {
      const { error } = await supabase
        .from('api_keys')
        .update({ is_active: false })
        .eq('id', keyId)

      if (error) throw error

      setKeys(keys.filter((k) => k.id !== keyId))
      router.refresh()
    } catch (err) {
      console.error('Failed to revoke key:', err)
      alert('Failed to revoke API key')
    }
  }

  const handleLogout = async () => {
    await supabase.auth.signOut()
    router.push('/login')
    router.refresh()
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    alert('Copied to clipboard!')
  }

  return (
    <div className="min-h-screen bg-[#0a0a0b]">
      {/* Header */}
      <header className="border-b border-zinc-800">
        <div className="max-w-6xl mx-auto px-4 py-4 flex justify-between items-center">
          <div className="flex items-center gap-4">
            <span className="text-xl font-bold">🌐 TranslateAPI</span>
            <span className="px-2 py-1 text-xs font-medium bg-blue-500/10 text-blue-400 rounded">
              {profile?.tier?.toUpperCase() || 'FREE'}
            </span>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-400">{user.email}</span>
            <button
              onClick={handleLogout}
              className="text-sm text-gray-400 hover:text-white transition"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8">
        {/* Usage Overview */}
        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-4">Usage This Month</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-6">
              <div className="text-sm text-gray-400 mb-2">API Requests</div>
              <div className="text-3xl font-bold mb-2">
                {requestCount.toLocaleString()} <span className="text-lg text-gray-500">/ {requestLimit.toLocaleString()}</span>
              </div>
              <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${usagePercent > 90 ? 'bg-red-500' : usagePercent > 70 ? 'bg-yellow-500' : 'bg-blue-500'}`}
                  style={{ width: `${usagePercent}%` }}
                />
              </div>
            </div>

            <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-6">
              <div className="text-sm text-gray-400 mb-2">Characters Translated</div>
              <div className="text-3xl font-bold">
                {(monthlyUsage?.characters_total || 0).toLocaleString()}
              </div>
            </div>

            <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-6">
              <div className="text-sm text-gray-400 mb-2">Audio Processed</div>
              <div className="text-3xl font-bold">
                {(monthlyUsage?.audio_seconds_total || 0).toFixed(1)}s
              </div>
            </div>
          </div>
        </section>

        {/* API Keys */}
        <section className="mb-8">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold">API Keys</h2>
          </div>

          {/* New Key Display */}
          {newKey && (
            <div className="mb-4 p-4 bg-green-500/10 border border-green-500/20 rounded-lg">
              <div className="flex justify-between items-start mb-2">
                <div>
                  <div className="text-sm text-green-400 font-medium mb-1">
                    ✓ New API Key Generated
                  </div>
                  <div className="text-xs text-gray-400">
                    Copy this key now. You won't be able to see it again!
                  </div>
                </div>
                <button
                  onClick={() => setNewKey(null)}
                  className="text-gray-400 hover:text-white"
                >
                  ✕
                </button>
              </div>
              <div className="flex items-center gap-2 mt-3">
                <code className="flex-1 p-3 bg-black/50 rounded font-mono text-sm text-green-400 break-all">
                  {newKey}
                </code>
                <button
                  onClick={() => copyToClipboard(newKey)}
                  className="px-4 py-3 bg-green-600 hover:bg-green-700 rounded font-medium transition"
                >
                  Copy
                </button>
              </div>
            </div>
          )}

          {/* Generate New Key */}
          <div className="mb-4 p-4 bg-zinc-900 border border-zinc-800 rounded-lg">
            <div className="flex gap-4 items-end">
              <div className="flex-1">
                <label className="block text-sm text-gray-400 mb-2">Key Name</label>
                <input
                  type="text"
                  value={keyName}
                  onChange={(e) => setKeyName(e.target.value)}
                  className="w-full px-4 py-2 bg-zinc-800 border border-zinc-700 rounded focus:outline-none focus:border-blue-500"
                  placeholder="e.g., Production, Development"
                />
              </div>
              <button
                onClick={handleGenerateKey}
                disabled={loading}
                className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded font-medium transition"
              >
                {loading ? 'Generating...' : 'Generate New Key'}
              </button>
            </div>
          </div>

          {/* Existing Keys */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-zinc-800">
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">Name</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">Key</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">Created</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">Last Used</th>
                  <th className="text-right px-4 py-3 text-sm font-medium text-gray-400">Action</th>
                </tr>
              </thead>
              <tbody>
                {keys.filter(k => k.is_active).map((key) => (
                  <tr key={key.id} className="border-b border-zinc-800 last:border-0">
                    <td className="px-4 py-3">{key.name}</td>
                    <td className="px-4 py-3">
                      <code className="text-sm text-gray-400 font-mono">{key.key_prefix}</code>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-400">
                      {new Date(key.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-400">
                      {key.last_used_at
                        ? new Date(key.last_used_at).toLocaleDateString()
                        : 'Never'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => handleRevokeKey(key.id)}
                        className="text-sm text-red-400 hover:text-red-300 transition"
                      >
                        Revoke
                      </button>
                    </td>
                  </tr>
                ))}
                {keys.filter(k => k.is_active).length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-gray-500">
                      No API keys yet. Generate one above to get started.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* Recent Activity */}
        <section>
          <h2 className="text-xl font-semibold mb-4">Recent Activity</h2>
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-zinc-800">
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">Time</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">Endpoint</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">Characters</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">Response Time</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">Status</th>
                </tr>
              </thead>
              <tbody>
                {recentUsage.map((usage) => (
                  <tr key={usage.id} className="border-b border-zinc-800 last:border-0">
                    <td className="px-4 py-3 text-sm text-gray-400">
                      {new Date(usage.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3">
                      <code className="text-sm">{usage.endpoint}</code>
                    </td>
                    <td className="px-4 py-3 text-sm">
                      {usage.characters_translated}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-400">
                      {usage.response_time_ms}ms
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-sm ${usage.status_code === 200 ? 'text-green-400' : 'text-red-400'}`}>
                        {usage.status_code}
                      </span>
                    </td>
                  </tr>
                ))}
                {recentUsage.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-gray-500">
                      No API calls yet. Use your API key to make requests.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* Quick Start */}
        <section className="mt-8">
          <h2 className="text-xl font-semibold mb-4">Quick Start</h2>
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-6">
            <pre className="text-sm text-gray-300 overflow-x-auto">
{`curl -X POST "https://api.translateapi.dev/v1/translate" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "text": "Hello, world!",
    "source_lang": "eng_Latn",
    "target_lang": "fra_Latn"
  }'`}
            </pre>
          </div>
        </section>
      </main>
    </div>
  )
}
