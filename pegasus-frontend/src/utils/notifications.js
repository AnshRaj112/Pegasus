/** Browser notifications for validation completion. */

export async function requestNotificationPermission() {
  if (typeof window === 'undefined' || !('Notification' in window)) {
    return 'unsupported'
  }
  if (Notification.permission === 'granted') return 'granted'
  if (Notification.permission === 'denied') return 'denied'
  try {
    return await Notification.requestPermission()
  } catch {
    return 'denied'
  }
}

export function notifyValidationComplete({
  title,
  body,
  isMatch = true,
  onClick,
}) {
  if (typeof window === 'undefined' || !('Notification' in window)) return
  if (Notification.permission !== 'granted') return
  try {
    const notification = new Notification(title, {
      body,
      icon: '/photo.jpg',
      tag: `pegasus-validation-${Date.now()}`,
    })
    if (typeof onClick === 'function') {
      notification.onclick = () => {
        window.focus()
        onClick()
        notification.close()
      }
    }
  } catch {
    // ignore notification failures
  }
}
