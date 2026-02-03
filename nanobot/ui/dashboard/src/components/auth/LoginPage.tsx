import { useState, useRef, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import { 
  Lock, 
  Eye, 
  EyeOff, 
  AlertCircle, 
  Loader2,
  KeyRound,
  ArrowRight
} from 'lucide-react'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'

interface LoginPageProps {
  onLoginSuccess: () => void
}

type LoginStep = 'password' | 'pin'

export function LoginPage({ onLoginSuccess }: LoginPageProps) {
  const [step, setStep] = useState<LoginStep>('password')
  const [password, setPassword] = useState('')
  const [pin, setPin] = useState('')
  const [tempToken, setTempToken] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  
  const passwordRef = useRef<HTMLInputElement>(null)
  const pinRefs = useRef<(HTMLInputElement | null)[]>([])
  
  // Focus password input on mount
  useEffect(() => {
    passwordRef.current?.focus()
  }, [])
  
  // Focus first PIN input when entering PIN step
  useEffect(() => {
    if (step === 'pin') {
      pinRefs.current[0]?.focus()
    }
  }, [step])
  
  // Login mutation (password step)
  const loginMutation = useMutation({
    mutationFn: (password: string) => 
      fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      }).then(res => res.json()),
    onSuccess: (data) => {
      if (data.error) {
        setError(data.error)
        return
      }
      
      if (data.require_pin) {
        setTempToken(data.temp_token)
        setStep('pin')
        setError('')
      } else {
        // No PIN required, login successful
        onLoginSuccess()
      }
    },
    onError: (err: Error) => {
      setError(err.message || 'Login failed')
    },
  })
  
  // PIN verification mutation
  const verifyPinMutation = useMutation({
    mutationFn: (pin: string) =>
      fetch('/api/auth/verify-pin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ temp_token: tempToken, pin }),
      }).then(res => res.json()),
    onSuccess: (data) => {
      if (data.error) {
        setError(data.error)
        setPin('')
        // Refocus first PIN input
        pinRefs.current[0]?.focus()
        return
      }
      
      // Login successful
      onLoginSuccess()
    },
    onError: (err: Error) => {
      setError(err.message || 'PIN verification failed')
      setPin('')
    },
  })
  
  const handlePasswordSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    
    if (!password) {
      setError('Password is required')
      return
    }
    
    loginMutation.mutate(password)
  }
  
  const handlePinChange = (index: number, value: string) => {
    // Only allow digits
    if (value && !/^\d$/.test(value)) return
    
    const newPin = pin.split('')
    newPin[index] = value
    const updatedPin = newPin.join('')
    setPin(updatedPin)
    
    // Auto-focus next input
    if (value && index < 5) {
      pinRefs.current[index + 1]?.focus()
    }
    
    // Auto-submit when PIN is complete (6 digits)
    if (updatedPin.length === 6 && !updatedPin.includes('')) {
      verifyPinMutation.mutate(updatedPin)
    }
  }
  
  const handlePinKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace' && !pin[index] && index > 0) {
      pinRefs.current[index - 1]?.focus()
    }
  }
  
  const handleBackToPassword = () => {
    setStep('password')
    setPin('')
    setTempToken('')
    setError('')
    setTimeout(() => passwordRef.current?.focus(), 100)
  }
  
  const isLoading = loginMutation.isPending || verifyPinMutation.isPending

  return (
    <div className="min-h-screen bg-giga-dark flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-giga-accent rounded-2xl flex items-center justify-center mx-auto mb-4">
            <span className="text-3xl">🤖</span>
          </div>
          <h1 className="text-2xl font-bold text-white">GigaBot</h1>
          <p className="text-gray-500 mt-1">Dashboard Login</p>
        </div>
        
        {/* Login Card */}
        <div className="bg-giga-card border border-sidebar-border rounded-2xl p-6">
          {step === 'password' ? (
            <form onSubmit={handlePasswordSubmit} className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  <Lock size={14} className="inline mr-2" />
                  Password
                </label>
                <div className="relative">
                  <input
                    ref={passwordRef}
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your password"
                    className="input w-full pr-12"
                    disabled={isLoading}
                    autoComplete="current-password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white transition-colors"
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>
              
              {error && (
                <div className="flex items-center gap-2 p-3 bg-giga-error/10 border border-giga-error/20 rounded-lg text-giga-error text-sm">
                  <AlertCircle size={16} />
                  {error}
                </div>
              )}
              
              <button
                type="submit"
                disabled={isLoading}
                className="btn-primary w-full flex items-center justify-center gap-2"
              >
                {isLoading ? (
                  <>
                    <Loader2 size={18} className="animate-spin" />
                    Verifying...
                  </>
                ) : (
                  <>
                    Continue
                    <ArrowRight size={18} />
                  </>
                )}
              </button>
            </form>
          ) : (
            <div className="space-y-6">
              <div className="text-center">
                <div className="w-12 h-12 bg-giga-accent/20 rounded-full flex items-center justify-center mx-auto mb-3">
                  <KeyRound size={24} className="text-giga-accent" />
                </div>
                <h2 className="text-lg font-semibold text-white">Enter PIN</h2>
                <p className="text-sm text-gray-500 mt-1">
                  Enter your 6-digit PIN to continue
                </p>
              </div>
              
              {/* PIN Input */}
              <div className="flex justify-center gap-2">
                {[0, 1, 2, 3, 4, 5].map((index) => (
                  <input
                    key={index}
                    ref={(el) => (pinRefs.current[index] = el)}
                    type="password"
                    inputMode="numeric"
                    maxLength={1}
                    value={pin[index] || ''}
                    onChange={(e) => handlePinChange(index, e.target.value)}
                    onKeyDown={(e) => handlePinKeyDown(index, e)}
                    disabled={isLoading}
                    className={cn(
                      'w-12 h-14 text-center text-xl font-bold rounded-lg',
                      'bg-giga-hover border-2 border-sidebar-border text-white',
                      'focus:border-giga-accent focus:outline-none transition-colors',
                      'disabled:opacity-50'
                    )}
                  />
                ))}
              </div>
              
              {error && (
                <div className="flex items-center justify-center gap-2 p-3 bg-giga-error/10 border border-giga-error/20 rounded-lg text-giga-error text-sm">
                  <AlertCircle size={16} />
                  {error}
                </div>
              )}
              
              {isLoading && (
                <div className="flex items-center justify-center gap-2 text-gray-400">
                  <Loader2 size={18} className="animate-spin" />
                  Verifying PIN...
                </div>
              )}
              
              <button
                type="button"
                onClick={handleBackToPassword}
                className="w-full text-sm text-gray-400 hover:text-white transition-colors"
              >
                ← Back to password
              </button>
            </div>
          )}
        </div>
        
        {/* Footer */}
        <p className="text-center text-xs text-gray-600 mt-6">
          Secure dashboard access
        </p>
      </div>
    </div>
  )
}
