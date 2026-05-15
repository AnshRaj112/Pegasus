import { UserOutlined } from '@ant-design/icons'

export default function Header({ activeSection, onSectionChange }) {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-[#E8E8E8] bg-gradient-to-r from-white via-[#FFFDEF] to-white shadow-sm">
      <div className="px-4 py-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between gap-4">
          {/* Left: Pegasus Logo */}
          <div className="flex items-center gap-3 flex-shrink-0">
            <h1 className="text-2xl font-extrabold tracking-tight text-slate-800 hidden sm:inline sm:text-3xl">
              Pegasus
            </h1>
            <img
              src="/Pegasus.png"
              alt="Pegasus logo"
              className="h-12 w-12 rounded-lg object-cover object-[50%_20%] sm:h-14 sm:w-14"
            />
          </div>

          {/* Center: Navigation Links */}
          <nav className="flex gap-2 sm:gap-4 absolute left-1/2 transform -translate-x-1/2">
            <button
              onClick={() => onSectionChange('validation')}
              className={`px-4 py-2 font-semibold text-sm rounded-lg transition-all duration-200 ${
                activeSection === 'validation'
                  ? 'bg-[#EB4C4C] text-white shadow-md'
                  : 'text-slate-600 hover:text-[#EB4C4C] hover:bg-slate-50'
              }`}
            >
              Validation
            </button>
            <button
              onClick={() => onSectionChange('history')}
              className={`px-4 py-2 font-semibold text-sm rounded-lg transition-all duration-200 ${
                activeSection === 'history'
                  ? 'bg-[#EB4C4C] text-white shadow-md'
                  : 'text-slate-600 hover:text-[#EB4C4C] hover:bg-slate-50'
              }`}
            >
              History
            </button>
          </nav>

          {/* Right: User Profile */}
          <div className="flex items-center gap-3 flex-shrink-0 ml-auto">
            <div className="text-right hidden sm:block">
              <p className="text-sm font-semibold text-slate-800">User</p>
              <p className="text-xs text-slate-500">Profile</p>
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-full border-2 border-[#EB4C4C] bg-[#EB4C4C]/10 text-[#EB4C4C] sm:h-12 sm:w-12">
              <UserOutlined className="text-lg sm:text-xl" />
            </div>
          </div>
        </div>
      </div>
    </header>
  )
}
