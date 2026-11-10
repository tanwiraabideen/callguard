// Remembers the demo passcode for this tab. Browser storage can be unavailable,
// so the value is also kept in memory.

const STORAGE_KEY = "callguard-passcode";
let passcode = "";

export function getPasscode(): string {
  if (!passcode) {
    try {
      passcode = sessionStorage.getItem(STORAGE_KEY) ?? "";
    } catch {
      // Without storage, the page simply asks again after a reload.
    }
  }
  return passcode;
}

export function setPasscode(value: string) {
  passcode = value;
  try {
    sessionStorage.setItem(STORAGE_KEY, value);
  } catch {
    // Kept in memory only.
  }
}

export function passcodeHeaders(): Record<string, string> {
  return { "X-Demo-Passcode": getPasscode() };
}
