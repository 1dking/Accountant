/**
 * Keypad tab — direct render of KeypadView. Lives in tabs/ so the
 * 5-tab nav imports a consistent shape (every tab is a single file
 * under tabs/), but defers to the existing KeypadView for the
 * actual surface (which is also reused as the drawer body during
 * call states).
 */
import KeypadView from '../panels/KeypadView'

interface Props {
  number: string
  setNumber: (n: string) => void
  onDigit: (digit: string) => void
  onBackspace: () => void
  onCall: () => void
  disabled: boolean
}

export default function KeypadTab(props: Props) {
  return <KeypadView {...props} />
}
